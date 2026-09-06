# HA Server Monitor Home Assistant integration

A custom Home Assistant integration (domain `ha_server_monitor`) that turns
whatever a paired agent (the `ha-server-monitor-agent` project) reports into
real HA devices — one per physical disk/RAID array, with a child device per
filesystem mounted on it. The integration itself is generic: no hardcoded
knowledge of any particular host's disks, it just renders whatever ids show
up in the payloads it receives. **One config entry per paired agent host**
— you can pair it with several machines, each gets its own device tree.

## What you get, per paired host

- One device per physical disk or RAID array (`type`, `description`,
  **Health** — live, self-correcting — and **Alert** — latched, cleared via
  a **Clear alert** button).
- One child device per filesystem mounted on it (`fs_type`, **Total space**,
  **Free space**, **Low space** — live, threshold configurable via the
  integration's Options).

## How pairing works

The agent ships knowing nothing about Home Assistant (see the
`ha-server-monitor-agent` project's README). This integration finds it and
hands it what it needs:

1. It advertises itself via mDNS as `_ha-server-monitor._tcp.local.`. Settings →
   Devices & Services should show a "Discovered" prompt automatically once
   the agent is running — confirm it to pair.
2. If mDNS doesn't reach it (different subnet, Avahi not running, etc.), use
   Add Integration → HA Server Monitor manually and enter the agent's host/IP +
   port (default `8477`).
3. Either way, this integration then generates a webhook + a token and calls
   the agent's own `/register` endpoint with them — the agent persists that
   and starts reporting. No URL or token ever needs to be typed in by hand on
   either side.
4. Options (gear icon on the integration entry) → **Low free space alert
   threshold (%)** — default 10, applies live, no restart needed.

Re-pairing an agent that's already paired (e.g. moved to a new HA instance)
requires clearing its state file first — see the `ha-server-monitor-agent`
project's README — since `/register` only succeeds once per agent.

## Installing the integration itself

**Via HACS (recommended)**: this repo is public and carries real GitHub
Releases, so it can be added as a HACS custom repository:

1. HACS → Integrations → ⋮ (top right) → **Custom repositories**.
2. Repository: `ha-linux-monitoring/ha-server-monitor`, Category: **Integration**.
3. Find "HA Server Monitor" in the HACS store and **Download**.
4. Restart Home Assistant Core.

Updates then show up in HACS like any other tracked integration —
`installed_version`/`available_version` track real release tags (e.g.
`v1.0.0`), not raw commits, since this repo publishes proper GitHub
Releases matching `manifest.json`'s `version`.

**Direct install (no HACS)** — useful for bootstrapping a fresh instance
before HACS itself is set up:

1. `./deploy.sh <user>@<ha-host>` — copies `custom_components/ha_server_monitor/`
   into the target instance's config directory (default
   `/var/lib/homeassistant/homeassistant`; pass a second argument to
   override).
2. Restart Home Assistant Core (`ha core restart` on a Supervised install).

Either way, then install and start the agent on each host you want to
monitor (see the `ha-server-monitor-agent` project's README), and pair it
per "How pairing works" above.

## Updating

**Via HACS**: click Update on the integration's HACS card, restart Core.

**Direct install**: re-run `./deploy.sh` and restart Core.

Either way, devices/entities are keyed by a combination of the config entry
and the agent's reported ids, so updating doesn't create duplicates for
hosts that are already paired — and switching from a direct install to
HACS management (or back) is just a file swap in `custom_components/`,
it doesn't touch existing config entries, devices, or their assigned areas.

## Shipping a new release

Bump `manifest.json`'s `version`, commit, push to `main`, then cut a
matching GitHub Release (tag `vX.Y.Z`) — that's what HACS actually tracks
for update notifications, not raw commits on `main`.
