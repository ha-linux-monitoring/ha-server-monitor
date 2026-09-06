"""Shared DeviceInfo builders for HA Server Monitor entities.

Device identifiers and entity unique_ids are namespaced by config entry_id,
not just the raw physical/filesystem id from the agent's payload: since one
HA instance can pair with multiple agent hosts, and disk names like "sda" are
extremely common across unrelated machines, an id alone isn't safe as a
global key -- two different hosts' "sda" devices would otherwise collide
into one. entry_id is namespacing for uniqueness; hostname (the paired
agent's, not the literal domain name) is what's actually shown to the user.
"""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def namespaced_id(entry_id: str, raw_id: str) -> str:
    """Build a globally-unique key from a per-agent-payload id."""
    return f"{entry_id}_{raw_id}"


def physical_device_info(
    entry_id: str, hostname: str, physical_id: str, model: str
) -> DeviceInfo:
    """DeviceInfo for a physical storage device (a disk or a RAID array)."""
    return DeviceInfo(
        identifiers={(DOMAIN, namespaced_id(entry_id, physical_id))},
        name=f"{hostname} {physical_id}",
        manufacturer="HA Server Monitor",
        model=model,
    )


def filesystem_device_info(
    entry_id: str, hostname: str, fs_id: str, parent_id: str, mount_point: str
) -> DeviceInfo:
    """DeviceInfo for a filesystem device, linked as a child of its physical device.

    Named after fs_id, not the raw mount_point: a mount point of "/" slugifies
    to nothing useful (it has no alphanumeric characters), which previously
    collapsed the root filesystem's entity_ids down to no distinguishing
    prefix at all. mount_point is still shown via the device's model field.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, namespaced_id(entry_id, fs_id))},
        name=f"{hostname} {fs_id}",
        manufacturer="HA Server Monitor",
        model=f"filesystem ({mount_point})",
        via_device=(DOMAIN, namespaced_id(entry_id, parent_id)),
    )
