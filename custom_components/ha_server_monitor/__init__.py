"""The HA Server Monitor integration.

Owns a webhook that a paired agent (see the ha-server-monitor-agent project)
posts storage topology snapshots to (physical devices + filesystems, plus an
optional event block for mdadm/smartd-triggered alerts). Pairing happens
during the config flow (zeroconf discovery or manual host/IP entry) -- see
config_flow.py -- which calls the agent's own /register endpoint to hand it
this webhook's URL plus a token. Every request on this webhook must carry
that same token as `Authorization: Bearer <token>`; anything else is
rejected. See hub.py for how an authenticated payload turns into
devices/entities.
"""

from __future__ import annotations

import hmac
import logging

from aiohttp import web

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import HaServerMonitorHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Server Monitor from a config entry."""
    hostname = entry.data.get("hostname", entry.title)
    hub = HaServerMonitorHub(hass, entry.entry_id, hostname)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    # Forward to platforms first so their dispatcher listeners are live
    # before the webhook can possibly receive its first payload.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    webhook_id = entry.data["webhook_id"]
    expected_token = entry.data["token"]

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response | None:
        auth = request.headers.get("Authorization", "")
        provided = auth[7:] if auth.startswith("Bearer ") else ""
        if not hmac.compare_digest(provided, expected_token):
            _LOGGER.warning("Rejected HA Server Monitor webhook request: bad/missing token")
            return web.Response(status=401, text="invalid token")
        try:
            data = await request.json()
        except ValueError:
            _LOGGER.warning("Received non-JSON body on HA Server Monitor webhook")
            return web.Response(status=400, text="expected JSON body")
        hub.handle_payload(data)
        return web.Response(status=200)

    webhook.async_register(
        hass, DOMAIN, f"HA Server Monitor ({hostname})", webhook_id, handle_webhook, local_only=True
    )

    # No update listener/reload on options change: FilesystemLowSpaceSensor reads
    # entry.options live on every state evaluation, and HA mutates the same
    # ConfigEntry object in place when options change -- reloading the entry here
    # would just force every entity into "unavailable" until the next heartbeat,
    # for no benefit.
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an HA Server Monitor config entry."""
    webhook.async_unregister(hass, entry.data["webhook_id"])
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
