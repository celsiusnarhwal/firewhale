import json
import sys
from pathlib import Path

import inflect as ifl
import pendulum
from docker import DockerClient
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from rich.console import Console
from rich.padding import Padding
from rich.table import Table

from firewhale.settings import FirewhaleSettings
from firewhale.types import LogFormat, LogLevel, Matcher

settings = FirewhaleSettings()

jinja = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    trim_blocks=True,
    lstrip_blocks=True,
)

inflect = ifl.engine()


def generate():
    """
    Generate a Caddy configuration for Firewhale.
    """
    if settings.dev_mode and settings.dev_docker_opts:
        dc = DockerClient(**settings.dev_docker_opts)
    else:
        dc = DockerClient("unix:///var/run/docker.sock")

    logger.debug("Connected to Docker Engine")

    allowed_containers = []
    matchers = []

    for container in dc.containers.list():
        logger.debug(f"Determining access for {container.name}")

        read_label = container.labels.get(f"{settings.label_prefix}.read")
        write_label = container.labels.get(f"{settings.label_prefix}.write")

        if read_label or write_label:
            allowed_containers.append(container)

            # Write a request matcher for readable endpoints
            if read_label:
                readable_endpoints = [
                    endpoint.lstrip("/").casefold()
                    for endpoint in read_label.split(" ")
                ]

                rules = [f"remote_host nocache {container.name}", "method GET HEAD"]

                if "all" not in readable_endpoints:
                    logger.debug(
                        f"Granting {container.name} read access to "
                        + inflect.join(
                            [f"/{endpoint}" for endpoint in readable_endpoints]
                        )
                    )
                    rules.append("vars {endpoint} " + " ".join(readable_endpoints))
                else:
                    logger.debug(
                        f"Granting {container.name} read access to all endpoints"
                    )

                matchers.append(Matcher(name=f"{container.name}_read", rules=rules))

            # Write a request matcher for writeable endpoints
            if write_label:
                writeable_endpoints = [
                    endpoint.lstrip("/").casefold()
                    for endpoint in write_label.split(" ")
                ]

                rules = [f"remote_host nocache {container.name}"]

                if "all" not in writeable_endpoints:
                    logger.debug(
                        f"Granting {container.name} write access to "
                        + inflect.join(
                            [f"/{endpoint}" for endpoint in writeable_endpoints]
                        )
                    )
                    rules.append("vars {endpoint} " + " ".join(writeable_endpoints))
                else:
                    logger.debug(
                        f"Granting {container.name} write access to all endpoints"
                    )

                matchers.append(Matcher(name=f"{container.name}_write", rules=rules))
        else:
            logger.debug(f"No access granted to {container.name}")

    # Write a request matcher for /events, /_ping, and /version
    if allowed_containers:
        container_names = [ctr.name for ctr in allowed_containers]
        logger.debug(
            f"Granting read access to /events, /_ping, and /version to {inflect.join(container_names)}"
        )

        matchers.append(
            Matcher(
                name="basic",
                rules=[
                    "remote_host nocache " + " ".join(container_names),
                    "method GET HEAD",
                    "vars {endpoint} events _ping version",
                ],
            )
        )

    logger.debug("Generating Caddyfile")
    template = jinja.get_template("Caddyfile.template.txt")
    caddyfile = template.render(matchers=matchers, settings=settings)

    return caddyfile


def log_sink(log: str):
    # Since Caddy is the only other thing logging to the container, we try our best to mimic its log structure.
    record = json.loads(log)["record"]

    level: LogLevel = LogLevel(record["level"]["name"])
    timestamp: float = record["time"]["timestamp"]
    name: str = "firewhale"
    message: str = record["message"]

    if settings.log_format is LogFormat.JSON:
        log = {
            "level": level.lower(),
            "ts": timestamp,
            "logger": name,
            "msg": message,
        }

        print(json.dumps(log), file=sys.stderr)
    else:
        time = pendulum.from_timestamp(record["time"]["timestamp"]).format(
            "YYYY/MM/DD HH:mm:ss.SSS"
        )
        level_color = {
            LogLevel.DEBUG: "violet",
            LogLevel.INFO: "blue",
            LogLevel.WARN: "yellow",
            LogLevel.ERROR: "red",
        }[level]

        table = Table.grid()
        table.add_row(
            Padding(time, (0, 1, 0, 0)),
            Padding(f"[{level_color}]{level}[/]", (0, 8 - len(level), 0, 0)),
            Padding(name, (0, 3, 0, 0)),
            message,
        )

        console = Console(stderr=True, width=10**100)
        console.print(table)

    if level is LogLevel.ERROR:
        sys.exit(1)
