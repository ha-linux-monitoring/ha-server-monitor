#!/bin/bash
# Usage: ./deploy.sh <user>@<ha-host> [ha-config-path]
#
# Copies custom_components/ha_server_monitor/ into a Home Assistant instance's
# custom_components directory. Default ha-config-path matches this project's
# known instance; pass a second argument to target a different one.
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <user>@<ha-host> [ha-config-path]" >&2
    exit 1
fi

TARGET="$1"
HA_CONFIG_PATH="${2:-/var/lib/homeassistant/homeassistant}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ssh "$TARGET" "mkdir -p /tmp/ha_server_monitor_deploy"
scp -r "$SCRIPT_DIR/custom_components/ha_server_monitor" "$TARGET:/tmp/ha_server_monitor_deploy/"
ssh "$TARGET" "
    rm -rf '$HA_CONFIG_PATH/custom_components/ha_server_monitor'
    cp -r /tmp/ha_server_monitor_deploy/ha_server_monitor '$HA_CONFIG_PATH/custom_components/ha_server_monitor'
    find '$HA_CONFIG_PATH/custom_components/ha_server_monitor' -name '__pycache__' -exec rm -rf {} +
    rm -rf /tmp/ha_server_monitor_deploy
"

cat <<EOF

Deployed to $TARGET:$HA_CONFIG_PATH/custom_components/ha_server_monitor/

Next: restart Home Assistant Core (e.g. 'ha core restart' on a Supervised
install) and, on first install, add the integration via Settings -> Devices
& Services -> Add Integration -> HA Server Monitor. It will generate a
webhook URL for you -- put that into the monitored host's
ha-server-monitor-agent install (see that project's README).
EOF
