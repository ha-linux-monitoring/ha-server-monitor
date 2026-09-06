"""Binary sensor entities for HA Server Monitor: health, alerts, low-space warnings."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_LOW_SPACE_THRESHOLD,
    DEFAULT_LOW_SPACE_THRESHOLD,
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
                PhysicalHealthSensor(hub, physical_id),
                PhysicalAlertSensor(hub, physical_id),
            ]
        )

    @callback
    def _add_filesystem(fs_id: str) -> None:
        async_add_entities([FilesystemLowSpaceSensor(hub, fs_id, entry)])

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

    for physical_id in hub.physical_devices:
        _add_physical(physical_id)
    for fs_id in hub.filesystems:
        _add_filesystem(fs_id)


class PhysicalHealthSensor(BinarySensorEntity):
    """Live, self-correcting: reflects the most recent heartbeat's own check."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "physical_health"

    def __init__(self, hub: HaServerMonitorHub, physical_id: str) -> None:
        self._hub = hub
        self._physical_id = physical_id
        self._attr_unique_id = f"{hub.entry_id}_{physical_id}_health"

    @property
    def device_info(self):
        state = self._hub.physical_devices[self._physical_id]
        return physical_device_info(
            self._hub.entry_id, self._hub.hostname, self._physical_id, state.type
        )

    @property
    def is_on(self) -> bool:
        return not self._hub.physical_devices[self._physical_id].healthy

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"detail": self._hub.physical_devices[self._physical_id].health_detail}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_PHYSICAL_UPDATED.format(self._physical_id),
                self.async_write_ha_state,
            )
        )


class PhysicalAlertSensor(BinarySensorEntity):
    """Latched: set by an mdadm/smartd event, only cleared via ClearAlert."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "physical_alert"

    def __init__(self, hub: HaServerMonitorHub, physical_id: str) -> None:
        self._hub = hub
        self._physical_id = physical_id
        self._attr_unique_id = f"{hub.entry_id}_{physical_id}_alert"

    @property
    def device_info(self):
        state = self._hub.physical_devices[self._physical_id]
        return physical_device_info(
            self._hub.entry_id, self._hub.hostname, self._physical_id, state.type
        )

    @property
    def is_on(self) -> bool:
        return self._hub.physical_devices[self._physical_id].alert

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"detail": self._hub.physical_devices[self._physical_id].alert_detail}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_PHYSICAL_UPDATED.format(self._physical_id),
                self.async_write_ha_state,
            )
        )


class FilesystemLowSpaceSensor(BinarySensorEntity):
    """Live: on when free space drops below the configured threshold."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "filesystem_low_space"

    def __init__(
        self, hub: HaServerMonitorHub, fs_id: str, entry: ConfigEntry
    ) -> None:
        self._hub = hub
        self._fs_id = fs_id
        self._entry = entry
        self._attr_unique_id = f"{hub.entry_id}_{fs_id}_low_space"

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

    def _free_percent(self) -> float | None:
        state = self._hub.filesystems[self._fs_id]
        if state.total_gb <= 0:
            return None
        return state.free_gb / state.total_gb * 100

    @property
    def is_on(self) -> bool:
        free_percent = self._free_percent()
        if free_percent is None:
            return False
        threshold = self._entry.options.get(
            CONF_LOW_SPACE_THRESHOLD, DEFAULT_LOW_SPACE_THRESHOLD
        )
        return free_percent < threshold

    @property
    def extra_state_attributes(self) -> dict[str, float]:
        free_percent = self._free_percent()
        return {"free_percent": round(free_percent, 1) if free_percent is not None else 0.0}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_FILESYSTEM_UPDATED.format(self._fs_id),
                self.async_write_ha_state,
            )
        )
