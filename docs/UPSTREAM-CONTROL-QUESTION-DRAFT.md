# Draft follow-up for issue #19

Thanks for the suggested clean-upstream comparison. We are preparing it on the same HP and macOS installation, and will record the exact loaded stack and panic if one occurs.

One compatibility question before changing the machine: the tested installation and previous control are **macOS 26.6.2 (25G83)**, while the current repository's `install.sh` at [`562e02ca4a207414dd849ea0c573d826f86b4901`](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/562e02ca4a207414dd849ea0c573d826f86b4901/install.sh) explicitly requires **26.7.1 (25G241)** and otherwise refuses without `XE_FORCE=1`. The installer also replaces system-wide graphics components, not just the EFI kext.

For the cleanest **same-OS** trial, do you have a current source revision / supported build procedure for 25G83, or a recommended minimal NootedGreen-only substitution against the existing installed TGL / HookCase / Metal stack? If the latter, which component versions and runtime checks should match to make the result interpretable? We would prefer not to override the build check or update macOS without understanding how the changed components affect the comparison.

We plan to record the exact source commit and binary hashes, actual OS build, loaded components and effective `ngreen-eu=80 ngreen-l3=6` topology. A panic will be preserved in full; a run longer than five minutes will be reported as an observation window rather than proof of stability.

This is a draft; no comment has been posted.
