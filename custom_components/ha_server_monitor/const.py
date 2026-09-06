"""Constants for the HA Server Monitor integration."""

DOMAIN = "ha_server_monitor"

CONF_LOW_SPACE_THRESHOLD = "low_space_threshold_percent"
DEFAULT_LOW_SPACE_THRESHOLD = 10

# Dispatcher signals. Each is formatted with an id before use:
# - the *_NEW_* signals are scoped per config entry (a new physical device/filesystem
#   was discovered in a payload) so each platform's async_setup_entry can add entities.
# - the *_UPDATED signals are scoped per physical/filesystem id, so only the entities
#   belonging to that specific device refresh their state.
SIGNAL_NEW_PHYSICAL = f"{DOMAIN}_new_physical_{{}}"
SIGNAL_NEW_FILESYSTEM = f"{DOMAIN}_new_filesystem_{{}}"
SIGNAL_PHYSICAL_UPDATED = f"{DOMAIN}_physical_updated_{{}}"
SIGNAL_FILESYSTEM_UPDATED = f"{DOMAIN}_filesystem_updated_{{}}"
