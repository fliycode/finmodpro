import os


def get_env(name, default=None):
    return os.getenv(name, default)


def get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def get_list_env(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]
