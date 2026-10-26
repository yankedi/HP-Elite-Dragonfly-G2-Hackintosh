# Provenance and reproducibility

`docs/provenance.json` is the machine-readable record for this phase.
`docs/provenance/<repo>-SHA256SUMS` is a sorted SHA-256 manifest of every
regular file in each pinned upstream working tree, excluding `.git/`.

Reproduce the check:

```sh
cd inputs/upstream/julio-xps13
sha256sum -c ../../../docs/provenance/julio-xps13-SHA256SUMS
```

The manifests were generated on 2026-10-22 with:

```sh
git clone --depth 1 --single-branch <url> <id>
git -C <id> rev-parse HEAD
find <id> -path <id>/.git -prune -o -type f -print0 \
  | LC_ALL=C sort -z | xargs -0 sha256sum
```

`git clone` does not execute repository scripts, hooks from the remote, or
submodule code. No `install.sh`, build script with download logic, or target
deployment script was run.

The upstream trees are gitignored because the NootedGreen repository embeds
Apple proprietary binaries and because the complete trees are large. The
commit IDs plus manifests are the transferable evidence; the trees themselves
must be moved privately with their hashes if this work is migrated.
