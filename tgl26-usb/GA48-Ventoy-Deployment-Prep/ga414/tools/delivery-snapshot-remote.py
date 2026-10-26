#!/usr/bin/env python3
"""Read-only snapshot of protected images and installed stack on the Mac."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''): digest.update(block)
    return digest.hexdigest()


def main():
    volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/TARGET_VOLUME']))
    if volume['VolumeUUID'] != 'REDACTED-SESSION-ID': raise RuntimeError('wrong USB volume')
    names = ['HP-Tahoe-TGL-GA410-R6-POOL.img', 'HP-Tahoe-TGL-GA410-R7-SURFACE.img',
             'HP-Tahoe-VESA-XHCI-RHUB.img', 'HP-Tahoe-Recovery-GA410-CSR0.img']
    protected = {}
    for name in names:
        path = Path('/Volumes/TARGET_VOLUME/ISO/linux') / name
        protected[str(path)] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    paths = [Path('/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics'),
             Path('/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer'),
             Path('/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver'),
             Path('/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib')]
    # Include the actual existing compiler bridge/adapter and installed KC files, never modify them.
    compiler_roots = [Path('/System/Library/Caches/xe.bundle/Contents/MacOS'), Path('/Library/Caches/xe.bundle/Contents/MacOS')]
    for root in compiler_roots:
        if root.is_dir():
            paths.extend(p for p in root.iterdir() if p.is_file())
    paths.extend(p for p in Path('/Library/KernelCollections').glob('*.kc') if p.is_file())
    files = {str(p): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(set(paths))}
    loaded = subprocess.run(['/usr/bin/kmutil', 'showloaded'], capture_output=True, text=True, check=True)
    print(json.dumps({'USB_volume_UUID': volume['VolumeUUID'], 'USB_device': volume['DeviceIdentifier'],
                      'protected_images': protected, 'installed_files': files,
                      'boot_session': subprocess.check_output(['/usr/sbin/sysctl', '-n', 'kern.bootsessionuuid'], text=True).strip(),
                      'loaded': loaded.stdout, 'loaded_stderr': loaded.stderr}, indent=2))


if __name__ == '__main__':
    main()
