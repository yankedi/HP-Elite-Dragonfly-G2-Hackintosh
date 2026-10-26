# GA40 Intel/ANV build environment; all writable state stays under this project.
# Override the dependency search paths for the host toolchain in use.
GA40_ROOT="${GA40_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export GA40_ROOT
export PYTHONPATH="$GA40_ROOT/cache/intel-toolenv/lib${GA40_EXTRA_PYTHONPATH:+:$GA40_EXTRA_PYTHONPATH}${PYTHONPATH:+:$PYTHONPATH}"
if [[ -n ${GA40_EXTRA_PKG_CONFIG_PATH:-} ]]; then
  export PKG_CONFIG_PATH="$GA40_EXTRA_PKG_CONFIG_PATH${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
fi
export PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$GA40_ROOT/cache}"
export TMPDIR="${TMPDIR:-$GA40_ROOT/tmp}"
