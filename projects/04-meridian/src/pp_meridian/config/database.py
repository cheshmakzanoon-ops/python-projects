"""Parse PostgreSQL URLs without dropping libpq transport or authentication options."""

from typing import Any

from psycopg.conninfo import conninfo_to_dict


def database_config(url: str) -> dict[str, Any]:
    parameters = conninfo_to_dict(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parameters.pop("dbname", ""),
        "USER": parameters.pop("user", ""),
        "PASSWORD": parameters.pop("password", ""),
        "HOST": parameters.pop("host", "127.0.0.1"),
        "PORT": parameters.pop("port", "5432"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": parameters,
    }
