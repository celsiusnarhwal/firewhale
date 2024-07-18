import typing as t
from enum import StrEnum


class Matcher(t.TypedDict):
    name: str
    rules: list


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class LogFormat(StrEnum):
    JSON = "json"
    CONSOLE = "console"
