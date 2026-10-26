# GA42 offline constraint violation

The user authorized offline development, not new dependency downloads.
`logs/anv-040-meson-linux-parse/stdout.txt` records an accidental Meson probe
without `--wrap-mode=nodownload`. It downloaded:

* `http://zlib.net/fossils/zlib-1.3.1.tar.gz` and its WrapDB patch;
* `https://github.com/libexpat/libexpat/releases/download/R_2_5_0/expat-2.5.0.tar.xz`
  and its WrapDB patch.

The subsequent `Executing subproject` and dependency-success lines show these
were actual retrievals, not merely proposed URLs. They remain in ignored
GA42 work/cache evidence. Historical GA40/GA41 inputs were not edited. The
Linux configure success is excluded from Darwin build acceptance; the probe
is not repeated. No downloaded code is introduced into the driver patches.

The tracked attempt script now forces `--wrap-mode=nodownload`. This repairs
future behavior but cannot undo the original policy violation. Final strict
acceptance must record **UNMET** for the no-unauthorized-download criterion.
No original log is removed or relabeled, and no retroactive authorization is
assumed. No further download is requested or performed by this remediation.
