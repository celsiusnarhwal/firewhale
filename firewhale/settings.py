import typing as t

import durationpy
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FirewhaleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIREWHALE_")

    port: int = Field(2375, ge=0, le=65535)
    caddy_api_port: int = Field(2019, ge=0, le=65535)
    http_status_code: int = Field(403, ge=100, le=699)
    reload_interval: str = "30s"
    label_prefix: str = "firewhale"

    dev_mode: bool = False
    dev_docker_opts: t.Optional[dict] = None

    # noinspection PyMethodParameters
    @field_validator("reload_interval")
    def validate_reload_interval(cls, v):
        try:
            durationpy.from_str(v)
        except ValueError:
            raise ValueError(
                "FIREWHALE_RELOAD_INTERVAL must be in the format of a Go duration string. "
                "https://pkg.go.dev/time#ParseDuration"
            ) from None

        return v

    @property
    def reload_interval_seconds(self):
        seconds = durationpy.from_str(self.reload_interval).total_seconds()
        return int(seconds) if seconds.is_integer() else seconds
