"""Constants for the Gramps HA integration."""

DOMAIN = "gramps_ha"
DEFAULT_NAME = "Gramps HA"

CONF_URL = "url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_NUM_BIRTHDAYS = "num_birthdays"
CONF_SHOW_DEATHDAYS = "show_deathdays"
CONF_SHOW_ANNIVERSARIES = "show_anniversaries"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_NUM_BIRTHDAYS = 6
DEFAULT_SHOW_DEATHDAYS = False
DEFAULT_SHOW_ANNIVERSARIES = False
DEFAULT_SCAN_INTERVAL = 7 * 24  # 7 days in hours

ATTR_PERSON_NAME = "person_name"
ATTR_BIRTH_DATE = "birth_date"
ATTR_AGE = "age"
ATTR_DAYS_UNTIL = "days_until"
