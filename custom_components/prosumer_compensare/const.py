"""Constants for Prosumer Compensare integration."""

DOMAIN = "prosumer_compensare"
STORAGE_KEY = "prosumer_compensare_baselines"
STORAGE_VERSION = 1

# Config flow keys - sensor entities
CONF_TOTAL_IMPORT = "total_energy_import"
CONF_TOTAL_EXPORT = "total_energy_export"
CONF_TODAY_IMPORT = "today_energy_import"
CONF_TODAY_EXPORT = "today_energy_export"
CONF_GRID_POWER = "grid_power"
CONF_PV_POWER = "pv_power"
CONF_BATTERY_SOC = "battery_soc"

# Config flow keys - prices & ratio
CONF_PRET_IMPORT = "pret_import"
CONF_PRET_EXPORT = "pret_export"
CONF_RAPORT = "raport_compensare"

# Defaults
DEFAULT_PRET_IMPORT = 1.16
DEFAULT_PRET_EXPORT = 0.464
DEFAULT_RAPORT = 2.5

# Compensation cycle starts March 1
CYCLE_START_MONTH = 3
CYCLE_START_DAY = 1
