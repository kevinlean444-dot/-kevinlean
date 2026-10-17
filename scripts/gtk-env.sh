# Source from the repository root: . scripts/gtk-env.sh
# Optional local Debian package extraction; normal distro installs need no overrides.
trama_runtime_root="$(pwd)/.runtime-gtk/root"
if [ -d "$trama_runtime_root/usr/lib/x86_64-linux-gnu" ]; then
    export XDG_CACHE_HOME="$(pwd)/.runtime-gtk/cache"
    export LD_LIBRARY_PATH="$trama_runtime_root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export GI_TYPELIB_PATH="$trama_runtime_root/usr/lib/x86_64-linux-gnu/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
    export XDG_DATA_DIRS="$trama_runtime_root/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
    export PATH="$trama_runtime_root/usr/bin:$PATH"
fi
unset trama_runtime_root
