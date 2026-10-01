#!/bin/sh
# Install an unpacked, verified release on a provisioned Pi OS Lite 64-bit host.
# Invoke explicitly on the target. Does not repartition, format or flash devices.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run on the target as root' >&2; exit 1; }
[ "$(uname -m)" = aarch64 ] || { echo 'Requires aarch64 Raspberry Pi OS Lite' >&2; exit 1; }
grep -q 'Raspberry Pi 4' /proc/device-tree/model || { echo 'Pi 4 target required' >&2; exit 1; }
sectors=$(cat /sys/class/block/mmcblk0/size)
[ "$((sectors * 512))" -ge 30000000000 ] || { echo 'A nominal 32 GB or larger SD card is required' >&2; exit 1; }
command -v uv >/dev/null || { echo 'Install the pinned uv version from the repository setup tooling first' >&2; exit 1; }
[ "$(uv --version)" = 'uv 0.12.18' ] || { echo 'Requires uv 0.12.18' >&2; exit 1; }
release=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
case "$release" in /opt/groundlark/releases/*) ;; *) echo 'Extract the bundle under /opt/groundlark/releases/<release-id> first' >&2; exit 1;; esac
cd "$release"
sha256sum -c SHA256SUMS
apt-get update
apt-get install -y caddy i2c-tools device-tree-compiler
caddy_version=$(caddy version | awk '{print $1}')
dpkg --compare-versions "${caddy_version#v}" ge 2.8.0 || { echo 'Caddy >=2.8 is required for basic_auth' >&2; exit 1; }
for group in groundlark groundlark-ui spi i2c gpio; do getent group "$group" >/dev/null || groupadd --system "$group"; done
id groundlark >/dev/null 2>&1 || useradd --system --gid groundlark --home-dir /var/lib/groundlark --shell /usr/sbin/nologin groundlark
id groundlark-ui >/dev/null 2>&1 || useradd --system --gid groundlark-ui --home-dir /var/lib/groundlark-ui --shell /usr/sbin/nologin groundlark-ui
install -d -m 0755 /opt/groundlark
install -d -m 0750 -o groundlark -g groundlark /var/lib/groundlark
install -d -m 0700 -o groundlark-ui -g groundlark-ui /var/lib/groundlark-ui
install -d -m 0750 -o root -g groundlark-ui /etc/groundlark
UV_PYTHON_INSTALL_DIR=/opt/groundlark/python UV_PROJECT_ENVIRONMENT="$release/.venv" uv sync --project sw/ui --frozen --python 3.12.12
# Every release owns its environment so rollback restores matching dependencies.
ln -sfn "$release" /opt/groundlark/current.next
mv -Tf /opt/groundlark/current.next /opt/groundlark/current
if [ ! -f /var/lib/groundlark/station.json ]; then
    install -m 0600 -o groundlark -g groundlark sw/pi/profiles/station-simulation.json /var/lib/groundlark/station.json
fi
# Both services need this token; UI has no direct bus or recording filesystem access.
if [ ! -f /etc/groundlark/runtime.env ]; then
    token=$("$release/.venv/bin/python" -c 'import secrets; print(secrets.token_hex(32))')
    printf 'GROUNDLARK_STATION_TOKEN=%s\nGROUNDLARK_DESCRIPTOR=/opt/groundlark/current/sw/build/schema.binpb\n' "$token" > /etc/groundlark/runtime.env
    chmod 0600 /etc/groundlark/runtime.env
fi
install -m 0644 sw/pi/deploy/groundlark-station.service sw/pi/deploy/groundlark-ui.service /etc/systemd/system/
install -d /etc/systemd/journald.conf.d
install -m 0644 sw/pi/deploy/groundlark-journald.conf /etc/systemd/journald.conf.d/groundlark.conf
systemctl daemon-reload
echo 'Installed. Configure LAN TLS/authentication, verify GPIO deployment and select source profiles before enabling services.'
echo 'Start with: systemctl enable --now groundlark-station groundlark-ui'
