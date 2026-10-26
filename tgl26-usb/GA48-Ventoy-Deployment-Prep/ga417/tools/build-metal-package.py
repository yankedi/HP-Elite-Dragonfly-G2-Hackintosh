#!/usr/bin/env python3
"""Build a standalone, reversible POSH bundle; never install on the HP."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga417/private'
REPORTS = ROOT / 'ga417/reports'
spec = importlib.util.spec_from_file_location('common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
NAME = 'AppleIntelTGLGraphicsMTLDriver.bundle'
EXEC = 'Contents/MacOS/AppleIntelTGLGraphicsMTLDriver'


def verify_signature(bundle):
    """Check ad-hoc CodeDirectory page/special hashes, not Apple trust policy."""
    raw = (bundle / EXEC).read_bytes()
    pos = 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, size = struct.unpack_from('<II', raw, pos)
        if cmd == 0x1d:
            start, length = struct.unpack_from('<II', raw, pos + 8)
            break
        pos += size
    else:
        raise AssertionError('Missing LC_CODE_SIGNATURE')
    sig = raw[start:start+length]
    magic, total, count = struct.unpack_from('>III', sig)
    assert magic == 0xfade0cc0 and total <= length
    blobs = {}
    for i in range(count):
        slot, off = struct.unpack_from('>II', sig, 12+8*i)
        n = struct.unpack_from('>I', sig, off+4)[0]
        blobs[slot] = sig[off:off+n]
    cd = blobs[0]
    magic, length, version, flags, hashoff, identoff, nspecial, ncode, limit = struct.unpack_from('>9I', cd)
    hsize, htype, platform, page = struct.unpack_from('4B', cd, 36)
    assert magic == 0xfade0c02 and flags & 2 and hsize == 32 and htype == 2
    assert limit == start and page == 12 and ncode == (limit+4095)//4096
    for i in range(ncode):
        assert hashlib.sha256(raw[i*4096:min((i+1)*4096,limit)]).digest() == cd[hashoff+i*hsize:hashoff+(i+1)*hsize]
    special = {1:(bundle/'Contents/Info.plist').read_bytes(), 2:blobs[2], 3:(bundle/'Contents/_CodeSignature/CodeResources').read_bytes()}
    for slot, b in special.items():
        assert nspecial >= slot
        assert hashlib.sha256(b).digest() == cd[hashoff-slot*hsize:hashoff-(slot-1)*hsize]
    return {'status':'ADHOC_CODEDIRECTORY_ALL_PAGES_AND_INFO_REQUIREMENTS_RESOURCES_HASHES_PASS',
            'signed_pages':ncode, 'code_limit':limit, 'cdhash_sha256_20':hashlib.sha256(cd).hexdigest()[:40],
            'identifier':cd[identoff:cd.index(b'\0',identoff)].decode(),
            'native_codesign_strict':'PENDING_MACOS', 'Apple_or_Developer_ID_trust':False}


def main():
    audit = json.loads((REPORTS/'METAL-POSH-AUDIT.json').read_text())
    assert audit['status'] == 'SAME_POSH_LEAK_CODE_PATH_CONFIRMED_STATICALLY'
    original = WORK/'metal-baseline'/NAME
    before = c.inventory(original)
    assert before == audit['baseline_bundle_inventory']
    package = WORK/'GA417-Metal-POSH'
    package.mkdir()
    restore, candidate = package/'restore'/NAME, package/'candidate'/NAME
    shutil.copytree(original, restore)
    shutil.copytree(original, candidate)
    main_exe = candidate/EXEC
    raw = (original/EXEC).read_bytes()
    patched = bytearray(raw)
    assert patched[0x7ed87:0x7ed89] == bytes.fromhex('750d')
    patched[0x7ed87:0x7ed89] = bytes.fromhex('9090')
    main_exe.write_bytes(patched)
    assert [i for i,(a,b) in enumerate(zip(raw,patched)) if a!=b] == [0x7ed87,0x7ed88]
    sign = c.builder().SIGN
    # Keep CodeResources and existing nested dylibs byte-for-byte unchanged.
    # Main executable is not a resource entry. Sign it against the original seals.
    command = [sign,'sign','--config-file','/dev/null','--timestamp-url','none',
               '--binary-identifier',audit['CFBundleIdentifier'],
               '--info-plist-file',candidate/'Contents/Info.plist',
               '--code-resources-file',candidate/'Contents/_CodeSignature/CodeResources',main_exe]
    log = c.run(command)
    (WORK/'metal-sign.log').write_text(log)
    signed = main_exe.read_bytes()
    old_macho, new_macho = c.macho(raw), c.macho(signed)
    assert old_macho['uuid'] == new_macho['uuid']
    assert old_macho['sections'].keys() == new_macho['sections'].keys()
    for name, section in old_macho['sections'].items():
        new = new_macho['sections'][name]
        assert (section['address'],section['offset'],section['bytes']) == (new['address'],new['offset'],new['bytes'])
        off, size = section['offset'], section['bytes']
        expected = patched[off:off+size]
        assert signed[off:off+size] == expected, name
    # Load commands extend past 4096 in this image. Mask only the two sizes
    # that signing may change, then compare everything before LINKEDIT.
    normalized = bytearray(signed[:0x4a8000])
    pos = 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, size = struct.unpack_from('<II', raw, pos)
        assert signed[pos:pos+8] == raw[pos:pos+8]
        if cmd == 0x1d:
            normalized[pos+12:pos+16] = raw[pos+12:pos+16]
        if cmd == 0x19 and raw[pos+8:pos+24].rstrip(b'\0') == b'__LINKEDIT':
            normalized[pos+48:pos+56] = raw[pos+48:pos+56]
        pos += size
    assert normalized == patched[:0x4a8000]
    after = c.inventory(candidate)
    assert before.keys() == after.keys()
    assert [name for name in before if before[name]!=after[name]] == [EXEC]
    signature = verify_signature(candidate)
    signature_before = verify_signature(restore)
    assert signature['identifier'] == audit['CFBundleIdentifier']
    manifest = {'status':'OFFLINE_SIGNED_SINGLE_BRANCH_PACKAGE_NOT_INSTALLED',
        'only_functional_change':{'file_offset':'0x7ed87','before':'750d','after':'9090'},
        'upstream_commit':audit['upstream_commit'], 'baseline_inventory':before,'candidate_inventory':after,
        'baseline_executable_sha256':before[EXEC],'candidate_executable_sha256':after[EXEC],
        'MachO_UUID_unchanged':old_macho['uuid'],
        'all_MachO_sections_identical_except_two_POSH_bytes':True,
        'all_other_bundle_files_including_dylibs_and_CodeResources_unchanged':True,
        'existing_25G83_patches_preserved':True,'signature':signature,'restore_signature':signature_before,
        'native_codesign_strict':'NOT_RUN_HP_CURRENTLY_NIXOS','installed':False,'GPU_regression':'NOT_RUN',
        'restore_exact_baseline':True,'audit_report':str((REPORTS/'METAL-POSH-AUDIT.json').relative_to(ROOT))}
    c.save(package/'manifest.json',manifest)
    readme = '''# GA417 Metal POSH 单因素包

candidate/ 是独立签名候选，restore/ 是逐文件与原封存包一致的完整恢复bundle。
尚未安装；未重启；未做HP动态POSH计数或R8回归。

唯一功能修改：经本机hash与完整析构/初始化/queue所有权审计的主二进制
文件偏移0x7ed87，75 0d -> 90 90。其余Mach-O节（包括现有兼容性补丁）、
libxedrv/libigdmd、Info.plist、CodeResources完全不变；主文件签名重新生成。
UUID沿用原链接UUID，不能靠UUID区分；必须核对manifest中的完整SHA256。

这是实验性ad-hoc签名。离线CodeDirectory逐页及Info/Requirements/Resources
哈希校验通过；macOS原生codesign --verify --deep --strict尚待用户手动回macOS后执行。

切换前先采集当前完整bundle，核对主文件仍为manifest.baseline_executable_sha256，
并确认当前libxedrv等文件没有比封存版本更新。先在 `/Users/Shared` 下的独立目录解包并验证，
不要把本包直接覆盖当前唯一正常版本。保留本机原bundle备份以及restore目录；
后续部署只替换已审计的主二进制，并在目标macOS核对签名和全部其他文件hash。
本包不附自动安装器，不修改KC、EFI或NVRAM。

Metal实验使用原GA416引导（DisableRtcChecksum=false），不要用GA417 RTC对照镜像。
后续用户在场且系统健康时，先正常使用内存趋势观察，必要时仅限量空command buffer，
之后单次Metal基础/R8回归。不得自动上千次提交或循环压力测试。
POSH修复不代表pmap/wrong-zone/watchdog的内核根因已找到。
'''
    (package/'README.md').write_text(readme)
    (package/'SHA256SUMS').write_text(''.join(d+'  '+p+'\n' for p,d in c.inventory(package).items()))
    archive = WORK/'GA417-Metal-POSH-Fix-and-Restore.tar.gz'
    with tarfile.open(archive,'x:gz') as t:
        t.add(package,arcname=package.name)
    with tempfile.TemporaryDirectory(prefix='ga417-metal-',dir='/tmp/opencode') as temp:
        with tarfile.open(archive) as t:
            t.extractall(temp,filter='data')
        assert c.inventory(Path(temp)/package.name) == c.inventory(package)
        assert c.inventory(Path(temp)/package.name/'restore'/NAME) == before
        verify_signature(Path(temp)/package.name/'candidate'/NAME)
    assert c.inventory(original) == before
    c.save(REPORTS/'METAL-POSH-PACKAGE.json',dict(manifest,archive=c.record(archive),
        candidate=c.record(main_exe),restore=c.record(restore/EXEC),
        signing_tool=c.record(sign),signing_log=c.record(WORK/'metal-sign.log'),
        archive_readback_and_restore_roundtrip='PASS'))
    (WORK/(archive.name+'.sha256')).write_text(c.sha(archive)+'  '+archive.name+'\n')
    print(json.dumps({'archive':c.record(archive),'candidate':c.record(main_exe),'signature':signature},indent=2))


if __name__ == '__main__':
    main()
