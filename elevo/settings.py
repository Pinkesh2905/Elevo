import os
from importlib import import_module


ENVIRONMENT = os.getenv("ELEVO_ENV", "development").strip().lower()

MODULE_MAP = {
    "dev": "elevo.settings_development",
    "development": "elevo.settings_development",
    "staging": "elevo.settings_staging",
    "stage": "elevo.settings_staging",
    "prod": "elevo.settings_production",
    "production": "elevo.settings_production",
}

settings_module = MODULE_MAP.get(ENVIRONMENT, "elevo.settings_development")
loaded = import_module(settings_module)

for name in dir(loaded):
    if name.isupper():
        globals()[name] = getattr(loaded, name)

SETTINGS_ENVIRONMENT = ENVIRONMENT
