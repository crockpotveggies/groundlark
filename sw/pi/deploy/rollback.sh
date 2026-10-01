#!/bin/sh
# Explicit operator rollback; stops capture, restores an existing release and its venv.
set -eu
[ "$(id -u)" = 0 ] || exit 1
[ "$#" = 1 ] || { echo 'Usage: rollback.sh /opt/groundlark/releases/<release-id>' >&2; exit 1; }
release=$(realpath -e -- "$1")
case "$release" in /opt/groundlark/releases/*) ;; *) exit 1;; esac
[ -x "$release/.venv/bin/python" ] && [ -f "$release/SHA256SUMS" ]
(cd "$release" && sha256sum -c SHA256SUMS)
systemctl stop groundlark-ui groundlark-station
ln -sfn "$release" /opt/groundlark/current.next
mv -Tf /opt/groundlark/current.next /opt/groundlark/current
systemctl start groundlark-station groundlark-ui
