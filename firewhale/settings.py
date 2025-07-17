import typing as t
from functools import lru_cache

import durationpy
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from firewhale.types import LogFormat, LogLevel


class FirewhaleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIREWHALE_")

    port: int = Field(2375, ge=0, le=65535)
    caddy_api_port: int = Field(2019, ge=0, le=65535)
    http_status_code: int = Field(403, ge=100, le=599)
    reload_interval: str = "30s"
    label_prefix: str = "firewhale"
    log_level: LogLevel = LogLevel.INFO
    log_format: LogFormat = LogFormat.JSON

    dev_mode: bool = False
    dev_docker_opts: t.Optional[dict] = None

    @model_validator(mode="after")
    def validate_ports(self):
        if self.port == self.caddy_api_port:
            raise ValueError(
                "FIREWHALE_PORT and FIREWHALE_CADDY_API_PORT cannot be the same."
            )

        return self

    @model_validator(mode="after")
    def validate_reload_interval(self):
        try:
            _ = self.reload_interval_seconds
        except ValueError:
            raise ValueError(
                "FIREWHALE_RELOAD_INTERVAL must be in the format of a Go duration string. "
                "https://pkg.go.dev/time#ParseDuration"
            ) from None

        if self.reload_interval_seconds < 0:
            raise ValueError(
                f"FIREWHALE_RELOAD_INTERVAL may not be negative "
                f"({self.reload_interval} = {self.reload_interval_seconds})."
            )

        return self

    @property
    def caddy_admin_address(self):
        return f"localhost:{self.caddy_api_port}"

    @property
    def reload_interval_seconds(self):
        seconds = durationpy.from_str(self.reload_interval).total_seconds()
        return int(seconds) if seconds.is_integer() else seconds


@lru_cache
def settings() -> FirewhaleSettings:
    return FirewhaleSettings()
