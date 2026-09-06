"""Sensor entities for HA Server Monitor: device properties and space figures."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SIGNAL_FILESYSTEM_UPDATED,
    SIGNAL_NEW_FILESYSTEM,
    SIGNAL_NEW_PHYSICAL,
    SIGNAL_PHYSICAL_UPDATED,
)
from .entity import filesystem_device_info, physical_device_info
from .hub import HaServerMonitorHub


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub: HaServerMonitorHub = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _add_physical(physical_id: str) -> None:
        async_add_entities(
            [
                PhysicalTypeSensor(hub, physical_id),
                PhysicalDescriptionSensor(hub, physical_id),
            ]
        )

    @callback
    def _add_filesystem(fs_id: str) -> None:
        async_add_entities(
            [
                FilesystemTypeSensor(hub, fs_id),
                FilesystemTotalSpaceSensor(hub, fs_id),
                FilesystemFreeSpaceSensor(hub, fs_id),
            ]
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_NEW_PHYSICAL.format(entry.entry_id), _add_physical
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_NEW_FILESYSTEM.format(entry.entry_id), _add_filesystem
        )
    )

    # Anything already known (e.g. a config entry reload) needs its entities too.
    for physical_id in hub.physical_devices:
        _add_physical(physical_id)
    for fs_id in hub.filesystems:
        _add_filesystem(fs_id)


class _PhysicalSensorBase(SensorEntity):
    """Common shape for sensors describing a physical device."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: HaServerMonitorHub, physical_id: str, key: str) -> None:
        self._hub = hub
        self._physical_id = physical_id
        self._attr_unique_id = f"{hub.entry_id}_{physical_id}_{key}"
        self._attr_translation_key = f"physical_{key}"

    @property
    def device_info(self):
        state = self._hub.physical_devices[self._physical_id]
        return physical_device_info(
            self._hub.entry_id, self._hub.hostname, self._physical_id, state.type
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_PHYSICAL_UPDATED.format(self._physical_id),
                self.async_write_ha_state,
            )
        )


class PhysicalTypeSensor(_PhysicalSensorBase):
    def __init__(self, hub: EeeHomeserverHub, physical_id: str) -> None:
        super().__init__(hub, physical_id, "type")

    @property
    def native_value(self) -> str:
        return self._hub.physical_devices[self._physical_id].type


class PhysicalDescriptionSensor(_PhysicalSensorBase):
    def __init__(self, hub: EeeHomeserverHub, physical_id: str) -> None:
        super().__init__(hub, physical_id, "description")

    @property
    def native_value(self) -> str:
        return self._hub.physical_devices[self._physical_id].description


class _FilesystemSensorBase(SensorEntity):
    """Common shape for sensors describing a filesystem device."""

    _attr_has_entity_name = True

    def __init__(self, hub: HaServerMonitorHub, fs_id: str, key: str) -> None:
        self._hub = hub
        self._fs_id = fs_id
        self._attr_unique_id = f"{hub.entry_id}_{fs_id}_{key}"
        self._attr_translation_key = key

    @property
    def device_info(self):
        state = self._hub.filesystems[self._fs_id]
        return filesystem_device_info(
            self._hub.entry_id,
            self._hub.hostname,
            self._fs_id,
            state.parent_id,
            state.mount_point,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_FILESYSTEM_UPDATED.format(self._fs_id),
                self.async_write_ha_state,
            )
        )


class FilesystemTypeSensor(_FilesystemSensorBase):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: EeeHomeserverHub, fs_id: str) -> None:
        super().__init__(hub, fs_id, "filesystem_type")

    @property
    def native_value(self) -> str:
        return self._hub.filesystems[self._fs_id].fs_type


class _FilesystemSpaceSensorBase(_FilesystemSensorBase):
    _attr_native_unit_of_measurement = "GB"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1


class FilesystemTotalSpaceSensor(_FilesystemSpaceSensorBase):
    def __init__(self, hub: EeeHomeserverHub, fs_id: str) -> None:
        super().__init__(hub, fs_id, "total_space")

    @property
    def native_value(self) -> float:
        return self._hub.filesystems[self._fs_id].total_gb


class FilesystemFreeSpaceSensor(_FilesystemSpaceSensorBase):
    def __init__(self, hub: EeeHomeserverHub, fs_id: str) -> None:
        super().__init__(hub, fs_id, "free_space")

    @property
    def native_value(self) -> float:
        return self._hub.filesystems[self._fs_id].free_gb
