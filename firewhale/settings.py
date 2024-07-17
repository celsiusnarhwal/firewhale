import typing as t

import durationpy
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FirewhaleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIREWHALE_")

    port: int = Field(2375, ge=0, le=65535)
    caddy_api_port: int = Field(2019, ge=0, le=65535)
    http_status_code: int = Field(403, ge=100, le=599)
    reload_interval: str = "30s"
    label_prefix: str = "firewhale"

    dev_mode: bool = False
    dev_docker_opts: t.Optional[dict] = None

    @model_validator(mode="after")
    def validate_ports(self):
        if self.port == self.caddy_api_port:
            raise ValueError(
                "FIREWHALE_PORT and FIREWHALE_CADDY_API_PORT cannot be the same."
            )

    @classmethod
    @field_validator("reload_interval")
    def validate_reload_interval(cls, v):
        try:
            interval = durationpy.from_str(v)
        except ValueError:
            raise ValueError(
                "FIREWHALE_RELOAD_INTERVAL must be in the format of a Go duration string. "
                "https://pkg.go.dev/time#ParseDuration"
            ) from None

        if interval.total_seconds() < 0:
            raise ValueError(
                f"FIREWHALE_RELOAD_INTERVAL may not be negative ({v} = {interval.total_seconds()})."
            )

        return v

    @property
    def caddy_admin_address(self):
        return f"localhost:{self.caddy_api_port}"

    @property
    def reload_interval_seconds(self):
        seconds = durationpy.from_str(self.reload_interval).total_seconds()
        return int(seconds) if seconds.is_integer() else seconds
