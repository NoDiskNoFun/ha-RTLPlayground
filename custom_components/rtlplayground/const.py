"""Constants of the RTLPlayground integration."""

DOMAIN = "rtlplayground"

CONF_COUNTERS = "counters"
CONF_RATE_UNIT = "rate_unit"
# Option value -> unit (UnitOfDataRate.MEGABITS_PER_SECOND / MEGABYTES_PER_SECOND)
RATE_UNITS = {"mbit_s": "Mbit/s", "mbyte_s": "MB/s"}
DEFAULT_RATE_UNIT = "mbit_s"
RATE_SENSORS = ("rx_rate", "tx_rate")
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

MANUFACTURER = "RTLPlayground"

# Link modes as traffic.json reports them, mapped to the states of the
# link sensor
LINK_STATES = {
    "DOWN": "down",
    "10M": "10m",
    "100M": "100m",
    "500M": "500m",
    "1000M": "1g",
    "2.5G": "2_5g",
    "5G": "5g",
    "10G": "10g",
}
LINK_OPTIONS = list(dict.fromkeys(LINK_STATES.values()))

# Indices into counters.json, see doc/api.md
COUNTER_IN_OCTETS = 0
COUNTER_OUT_OCTETS = 1
