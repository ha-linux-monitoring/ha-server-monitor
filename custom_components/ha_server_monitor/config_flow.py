"""Config flow for HA Server Monitor.

One config entry per paired agent host (see the ha-server-monitor-agent
project's README for the pairing protocol). Two ways in converge on the
same pairing step:
- async_step_zeroconf: the agent was auto-discovered via mDNS.
- async_step_user: the user typed in the agent's host/IP + port by hand,
  for when mDNS doesn't reach it (different subnet, no Avahi, etc).
"""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.core import callback
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_LOW_SPACE_THRESHOLD, DEFAULT_LOW_SPACE_THRESHOLD, DOMAIN

DEFAULT_AGENT_PORT = 8477
_REQUEST_TIMEOUT = 5


def _fetch_info(host: str, port: int) -> dict[str, Any]:
    """Blocking GET agent/info -- always run via hass.async_add_executor_job."""
    with urllib.request.urlopen(
        f"http://{host}:{port}/info", timeout=_REQUEST_TIMEOUT
    ) as resp:
        return json.loads(resp.read())


def _register(host: str, port: int, webhook_url: str, token: str) -> None:
    """Blocking POST agent/register -- always run via hass.async_add_executor_job."""
    body = json.dumps({"webhook_url": webhook_url, "token": token}).encode()
    req = urllib.request.Request(
        f"http://{host}:{port}/register",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        resp.read()


class HaServerMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One entry per paired agent; unique_id is the agent's own hostname."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int = DEFAULT_AGENT_PORT
        self._hostname: str | None = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle an agent discovered via mDNS."""
        self._host = str(discovery_info.ip_address)
        self._port = discovery_info.port or DEFAULT_AGENT_PORT

        try:
            info = await self.hass.async_add_executor_job(
                _fetch_info, self._host, self._port
            )
        except OSError:
            return self.async_abort(reason="cannot_connect")

        self._hostname = info.get("hostname", self._host)
        await self.async_set_unique_id(self._hostname)
        self._abort_if_unique_id_configured(
            updates={"host": self._host, "port": self._port}
        )

        self.context["title_placeholders"] = {"name": self._hostname}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm pairing with a discovered agent."""
        if user_input is not None:
            return await self._async_pair_and_create_entry()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._hostname or "",
                "host": self._host or "",
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manual fallback: type in the agent's host/IP and port."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input["host"]
            self._port = user_input["port"]
            try:
                info = await self.hass.async_add_executor_job(
                    _fetch_info, self._host, self._port
                )
            except OSError:
                errors["base"] = "cannot_connect"
            else:
                self._hostname = info.get("hostname", self._host)
                await self.async_set_unique_id(self._hostname)
                self._abort_if_unique_id_configured(
                    updates={"host": self._host, "port": self._port}
                )
                return await self._async_pair_and_create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): str,
                    vol.Required("port", default=DEFAULT_AGENT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def _async_pair_and_create_entry(self) -> config_entries.ConfigFlowResult:
        """Generate a webhook + token and hand them to the agent's /register."""
        assert self._host is not None
        webhook_id = secrets.token_hex(16)
        token = secrets.token_urlsafe(32)
        webhook_url = webhook.async_generate_url(self.hass, webhook_id)

        try:
            await self.hass.async_add_executor_job(
                _register, self._host, self._port, webhook_url, token
            )
        except urllib.error.HTTPError as err:
            if err.code == 409:
                return self.async_abort(reason="already_paired")
            return self.async_abort(reason="cannot_connect")
        except OSError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=self._hostname or self._host,
            data={
                "webhook_id": webhook_id,
                "token": token,
                "hostname": self._hostname or self._host,
                "host": self._host,
                "port": self._port,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HaServerMonitorOptionsFlow:
        return HaServerMonitorOptionsFlow()


class HaServerMonitorOptionsFlow(config_entries.OptionsFlow):
    """Lets the low-space alert threshold be tuned without touching the host."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_LOW_SPACE_THRESHOLD, DEFAULT_LOW_SPACE_THRESHOLD
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOW_SPACE_THRESHOLD, default=current
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=99)),
                }
            ),
        )
