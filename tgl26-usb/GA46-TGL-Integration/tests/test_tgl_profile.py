#!/usr/bin/env python3
from pathlib import Path
root = Path(__file__).resolve().parent.parent
s = (root / 'src/NootedGreen/kern_gen11.cpp').read_text()
g = (root / 'src/NootedGreen/kern_green.cpp').read_text()
checks = {
    'native_identity': 'vendorId == 0x8086U' in g and 'deviceId == 0x9A49U' in g,
    'icl_spoof_rejected': 'propEquals("device-id", 0x8A5AU)' in g and '0x8A5C0002U' in g,
    'native_getter': 'getIsNativeTgl()' in g,
    'layout_master': 'xeTglLayoutEnabled(nullptr)' in s and '-ngreentgltahoe' in s,
    'fmt_independent': '-ngreennofmt' in s,
    'planes_default_off': '-ngreenplane2experimental' in s and '-ngreennoplanes2' in s,
    'vald_independent': '-ngreennovald' in s and 'GA4.5: XE-VALD' in s,
    'xefix_refused': 'GA4.5: -ngreenxefix refused on native TGL' in s,
    'forcewake_native': 'forceWakeAllowed' in s and 'ForceWake replacement/HANGCHECK skipped on native TGL' in s,
    'v40_refused': 'V40: skipped on native TGL' in g,
    'v221_refused': 'V221: skipped on native TGL' in g and 'refusing fake success' in g,
    'v500_skipped': 'V500: skipped on native TGL' in g,
    'weg_conflict': 'native TGL + WEG coexist' in s,
    'resfree_default_off': 'XE-RESFREE disabled on native TGL' in s,
    'gtfreq_native': 'getIsNativeTgl() && !checkKernelArgument("-ngreenallowrplfixes")' in s,
}
bad = [k for k, v in checks.items() if not v]
print(f"checks={len(checks)} failed={bad}")
raise SystemExit(1 if bad else 0)
