import json
import sys
import typing as t
from pathlib import Path

from docker import DockerClient
from jinja2 import Environment, FileSystemLoader

from firewhale.settings import FirewhaleSettings

settings = FirewhaleSettings()

jinja = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    trim_blocks=True,
    lstrip_blocks=True,
)


def generate():
    """
    Generate a Caddy configuration for Firewhale.
    """

    class Matcher(t.TypedDict):
        name: str
        rules: list

    if settings.dev_mode and settings.dev_docker_opts:
        dc = DockerClient(**settings.dev_docker_opts)
    else:
        dc = DockerClient("unix:///var/run/docker.sock")

    allowed_containers = []
    matchers = []

    for container in dc.containers.list():
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

                rules = [f"remote_host {container.name}", "method GET HEAD"]

                if "all" not in readable_endpoints:
                    rules.append("vars {endpoint} " + " ".join(readable_endpoints))

                matchers.append(Matcher(name=f"{container.name}_read", rules=rules))

            # Write a request matcher for writeable endpoints
            if write_label:
                writeable_endpoints = [
                    endpoint.lstrip("/").casefold()
                    for endpoint in write_label.split(" ")
                ]

                rules = [f"remote_host {container.name}"]

                if "all" not in writeable_endpoints:
                    rules.append("vars {endpoint} " + " ".join(writeable_endpoints))

                matchers.append(Matcher(name=f"{container.name}_write", rules=rules))

    # Write a request matcher for /events, /_ping, and /version
    if allowed_containers:
        matchers.append(
            Matcher(
                name="events_ping_version",
                rules=[
                    "remote_host " + " ".join([ctr.name for ctr in allowed_containers]),
                    "method GET HEAD",
                    "vars {endpoint} events _ping version",
                ],
            )
        )

    template = jinja.get_template("Caddyfile.template.txt")
    caddyfile = template.render(matchers=matchers, settings=settings)

    return caddyfile


def log_sink(log: str):
    record = json.loads(log)["record"]

    log = {
        "level": record["level"]["name"].lower(),
        "ts": record["time"]["timestamp"],
        "logger": "firewhale",
        "msg": record["message"],
    }

    print(json.dumps(log), file=sys.stderr)
