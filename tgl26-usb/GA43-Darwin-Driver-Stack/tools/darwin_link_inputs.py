"""Exact Darwin driver input closure for optional dispatch resolution.

Unknown or ambiguous inputs fail closed. Apple TBD documents are declarations
of dynamic exports; recursively follow their reexports, including embedded docs.
No symbols are invented. The final real linker still enforces strong imports.
"""
from pathlib import Path
import re
import struct
import subprocess
import sys

# Already present offline build dependency, not an installation or download.
sys.path.insert(0, '/nix/store/iw39pw567acajnaf1iywnwz6fwcb6cxg-python3.14-pyyaml-6.0.3/lib/python3.14/site-packages')
import yaml


class TBDLoader(yaml.SafeLoader):
    pass


TBDLoader.add_constructor('!tapi-tbd', lambda loader, node: loader.construct_mapping(node, deep=True))


def active(section):
    return 'x86_64-macos' in section.get('targets', [])


def dynamic_definitions(driver, build, nm):
    """Resolve actual ld64 argv, including Clang's implicit libc++ and System."""
    args = driver[1:]
    if '-syslibroot' not in args: raise ValueError('driver did not specify syslibroot')
    sdk = Path(args[args.index('-syslibroot')+1]).resolve()
    libraries, frameworks = [], []
    lpaths, fpaths = [], []
    def absolute(s):
        p = Path(s)
        return (p if p.is_absolute() else build/p).resolve()
    def choose(candidates):
        for group in candidates:
            found = {p.resolve() for p in group if p.is_file()}
            if len(found) > 1: raise ValueError('ambiguous dynamic input: '+str(found))
            if found: return found.pop()
        raise ValueError('missing dynamic input: '+str(candidates))
    i = 0
    while i < len(args):
        token = args[i]
        if token in ('-o', '-install_name', '-rpath', '-syslibroot'):
            i += 2; continue
        if token in ('-L', '-F'):
            (lpaths if token == '-L' else fpaths).append(absolute(args[i+1])); i += 2; continue
        if token.startswith('-L') or token.startswith('-F'):
            (lpaths if token[1] == 'L' else fpaths).append(absolute(token[2:]))
        elif token == '-framework':
            frameworks.append(args[i+1]); i += 2; continue
        elif token.startswith('-l'):
            if token == '-lto_library': raise ValueError('uninspected LTO provider')
            libraries.append(token[2:])
        elif token.endswith(('.dylib', '.tbd')):
            libraries.append(absolute(token))
        elif token.startswith(('-weak_', '-reexport_', '-lazy_', '-upward_')):
            raise ValueError('unsupported dynamic provider flag '+token)
        i += 1
    lpaths += [sdk/'usr/lib', sdk/'usr/local/lib']
    fpaths += [sdk/'System/Library/Frameworks', sdk/'Library/Frameworks']
    roots = set()
    for lib in libraries:
        if isinstance(lib, Path):
            if not lib.is_file(): raise ValueError('missing explicit dylib '+str(lib))
            roots.add(lib)
        else:
            roots.add(choose([[d/f'lib{lib}{suffix}' for suffix in ('.tbd', '.dylib', '.a')]
                              for d in lpaths]))
    for framework in frameworks:
        roots.add(choose([[d/f'{framework}.framework/{framework}{suffix}' for suffix in ('.tbd', '')]
                          for d in fpaths]))
    definitions, inspected, declarations = set(), set(), {}
    def resolve_install(name):
        if not name.startswith('/'): raise ValueError('unresolved dynamic reexport '+name)
        path = sdk/name.lstrip('/')
        if path.suffix == '.dylib': path = path.with_suffix('.tbd')
        elif not path.is_file(): path = Path(str(path)+'.tbd')
        if not path.is_file(): raise ValueError('missing reexport '+name)
        return path.resolve()
    seen_ids = set()
    def doc_visit(name):
        if name in seen_ids: return
        if name not in declarations:
            visit(resolve_install(name))
        if name not in declarations: raise ValueError('TBD install ID absent: '+name)
        seen_ids.add(name)
        doc = declarations[name]
        for section in doc.get('exports', []) + doc.get('reexports', []):
            if not active(section): continue
            for key in ('symbols', 'weak-symbols', 'thread-local-symbols'):
                definitions.update(section.get(key, []))
            for cls in section.get('objc-classes', []):
                definitions.update(('_OBJC_CLASS_$_'+cls, '_OBJC_METACLASS_$_'+cls))
        for section in doc.get('reexported-libraries', []):
            if active(section):
                for lib in section.get('libraries', []): doc_visit(lib)
    def visit(path):
        if path in inspected: return
        inspected.add(path)
        if path.suffix == '.tbd':
            docs = list(yaml.load_all(path.read_text(), Loader=TBDLoader))
            if not docs or any(d.get('tbd-version') != 4 for d in docs):
                raise ValueError('unsupported TBD schema '+str(path))
            for d in docs:
                if active(d): declarations[d['install-name']] = d
            if not active(docs[0]): raise ValueError('no x86_64-macos exports '+str(path))
            doc_visit(docs[0]['install-name'])
        else:
            # A binary input contributes only its actual defined externals.
            text = subprocess.check_output([nm, '-arch', 'x86_64', '-g', '-j', '--defined-only', str(path)], text=True)
            definitions.update(n for n in text.splitlines() if re.fullmatch(r'[A-Za-z_][\w$]*', n))
            if path.suffix == '.a': return
            b = path.read_bytes()
            if len(b) < 32 or struct.unpack_from('<I', b)[0] != 0xfeedfacf:
                raise ValueError('uninspected non-x86_64 dylib container '+str(path))
            count = struct.unpack_from('<I', b, 16)[0]
            at = 32
            for _ in range(count):
                cmd, size = struct.unpack_from('<II', b, at)
                if size < 8 or at+size > len(b): raise ValueError('invalid dylib command')
                if cmd == 0x8000001f:
                    off = struct.unpack_from('<I', b, at+8)[0]
                    if off >= size: raise ValueError('invalid reexport path')
                    visit(resolve_install(b[at+off:at+size].split(b'\0', 1)[0].decode()))
                at += size
    for path in sorted(roots): visit(path)
    return definitions, sorted(inspected)
