"""Shared state for the HA Server Monitor integration.

Devices and their properties are entirely payload-driven: the reporter script
running on the monitored host introspects its own storage topology and posts
a full snapshot on every push (heartbeat or event-triggered alike). The hub
never assumes a fixed set of physical devices/filesystems -- it diffs incoming
ids against what it already knows and signals platforms to add entities for
anything new.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    SIGNAL_FILESYSTEM_UPDATED,
    SIGNAL_NEW_FILESYSTEM,
    SIGNAL_NEW_PHYSICAL,
    SIGNAL_PHYSICAL_UPDATED,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PhysicalDeviceState:
    """Live state for one physical storage device (a disk or a RAID array)."""

    id: str
    type: str = "unknown"
    description: str = ""
    healthy: bool = True
    health_detail: str = ""
    alert: bool = False
    alert_detail: str = ""


@dataclass
class FilesystemState:
    """Live state for one mounted filesystem, a child of a physical device."""

    id: str
    parent_id: str = ""
    mount_point: str = ""
    fs_type: str = "unknown"
    total_gb: float = 0.0
    free_gb: float = 0.0


class HaServerMonitorHub:
    """Owns known physical devices/filesystems for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str, hostname: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        # Display name for this entry's devices -- the paired agent's hostname
        # (as reported by its /info endpoint), not the literal domain name,
        # since one HA instance can be paired with several agent hosts.
        self.hostname = hostname
        self.physical_devices: dict[str, PhysicalDeviceState] = {}
        self.filesystems: dict[str, FilesystemState] = {}

    def handle_payload(self, data: dict[str, Any]) -> None:
        """Apply an incoming webhook payload: physical devices, filesystems, then event."""
        for pd in data.get("physical_devices", []):
            self._update_physical(pd)

        for fs in data.get("filesystems", []):
            self._update_filesystem(fs)

        # Handled last so a physical device an event refers to is already
        # up to date from this same payload (the reporter always sends both).
        event = data.get("event")
        if event:
            self._handle_event(event)

    def _update_physical(self, pd: dict[str, Any]) -> None:
        pid = pd["id"]
        is_new = pid not in self.physical_devices
        state = self.physical_devices.setdefault(pid, PhysicalDeviceState(id=pid))
        state.type = pd.get("type", state.type)
        state.description = pd.get("description", state.description)
        state.healthy = pd.get("healthy", state.healthy)
        state.health_detail = pd.get("health_detail", state.health_detail)

        if is_new:
            _LOGGER.info("Discovered new HA Server Monitor physical device: %s", pid)
            async_dispatcher_send(
                self.hass, SIGNAL_NEW_PHYSICAL.format(self.entry_id), pid
            )
        else:
            async_dispatcher_send(self.hass, SIGNAL_PHYSICAL_UPDATED.format(pid))

    def _update_filesystem(self, fs: dict[str, Any]) -> None:
        fid = fs["id"]
        is_new = fid not in self.filesystems
        state = self.filesystems.setdefault(fid, FilesystemState(id=fid))
        state.parent_id = fs.get("parent_id", state.parent_id)
        state.mount_point = fs.get("mount_point", state.mount_point)
        state.fs_type = fs.get("fs_type", state.fs_type)
        state.total_gb = fs.get("total_gb", state.total_gb)
        state.free_gb = fs.get("free_gb", state.free_gb)

        if is_new:
            _LOGGER.info("Discovered new HA Server Monitor filesystem: %s", fid)
            async_dispatcher_send(
                self.hass, SIGNAL_NEW_FILESYSTEM.format(self.entry_id), fid
            )
        else:
            async_dispatcher_send(self.hass, SIGNAL_FILESYSTEM_UPDATED.format(fid))

    def _handle_event(self, event: dict[str, Any]) -> None:
        pid = event.get("physical_id")
        message = event.get("message", "")
        if not pid:
            _LOGGER.warning("HA Server Monitor event payload missing physical_id: %s", event)
            return
        state = self.physical_devices.setdefault(pid, PhysicalDeviceState(id=pid))
        state.alert = True
        state.alert_detail = message
        async_dispatcher_send(self.hass, SIGNAL_PHYSICAL_UPDATED.format(pid))

    def clear_alert(self, physical_id: str) -> None:
        """Reset a physical device's latched alert (called by its ClearAlert button)."""
        state = self.physical_devices.get(physical_id)
        if state is None:
            return
        state.alert = False
        state.alert_detail = ""
        async_dispatcher_send(self.hass, SIGNAL_PHYSICAL_UPDATED.format(physical_id))
