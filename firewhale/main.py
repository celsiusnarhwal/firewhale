import os
import subprocess
import sys
import typing as t
from pathlib import Path
from tempfile import TemporaryDirectory

import typer
import docker
import docker.errors
from jinja2 import Template
from loguru import logger
from pydantic import Field, TypeAdapter, ValidationError


class Matcher(t.TypedDict):
    name: str
    rules: list


HERE = Path(__file__).parent

app = typer.Typer(no_args_is_help=True)

dc = docker.DockerClient("unix://var/run/docker.sock")


@app.command("generate")
def generate(json: bool = typer.Option(False, "--json")):
    label_prefix = os.getenv("FIREWHALE_LABEL_PREFIX", "firewhale")

    # Validate FIREWHALE_PORT and FIREWHALE_HTTP_STATUS_CODE values
    port_ta = TypeAdapter(t.Annotated[int, Field(ge=0, le=65535)])
    status_code_ta = TypeAdapter(t.Annotated[int, Field(ge=100, le=599)])

    try:
        port = port_ta.validate_python(os.getenv("FIREWHALE_PORT", 2375))
    except ValidationError:
        raise ValueError(
            "FIREWHALE_PORT must be an integer between and 65535."
        ) from None

    try:
        fallback_status_code = status_code_ta.validate_python(
            os.getenv("FIREWHALE_HTTP_STATUS_CODE", 403)
        )
    except ValidationError:
        raise ValueError(
            "FIREWHALE_HTTP_STATUS_CODE must be an integer between 100 and 599."
        ) from None

    matchers = []

    try:
        firewhale = dc.containers.get(open("/etc/hostname").read().strip())
    except docker.errors.NotFound:
        try:
            firewhale = dc.containers.get(os.getenv("FIREWHALE_OVERRIDING_HOSTNAME"))
        except docker.errors.NotFound:
            raise docker.errors.NotFound(
                "Firewhale was unable to identify its own container. If you overrode the hostname of Firewhale's"
                "container, you must inform Firewhale of what the overriding hostname is via the "
                "FIREWHALE_OVERRIDING_HOSTNAME environment variable."
            ) from None

    firewhale_networks = firewhale.attrs["NetworkSettings"]["Networks"]

    for container in [ctr for ctr in dc.containers.list() if ctr is not firewhale]:
        container_networks = container.attrs["NetworkSettings"]["Networks"]
        reachable_networks = set(firewhale_networks.keys()).intersection(
            container_networks.keys()
        )

        if not reachable_networks:
            continue

        ip_addresses = [
            container_networks[network]["IPAddress"] for network in reachable_networks
        ]

        remote_ip_rule = "remote_ip " + " ".join(ip_addresses)

        read_label = container.labels.get(f"{label_prefix}.read")
        write_label = container.labels.get(f"{label_prefix}.write")

        # Write a request matcher for read access to /events, /_ping, and /version
        if read_label or write_label:
            matchers.append(
                Matcher(
                    name=f"{container.name}_basic",
                    rules=[
                        remote_ip_rule,
                        "method GET HEAD",
                        "vars {endpoint} events _ping version",
                    ],
                )
            )

            # Write a request matcher for GET and HEAD only
            if read_label:
                readable_endpoints = [
                    endpoint.lstrip("/").casefold()
                    for endpoint in read_label.split(" ")
                ]
                rules = [remote_ip_rule, "method GET HEAD"]

                if "all" not in readable_endpoints:
                    rules.append("vars {endpoint} " + " ".join(readable_endpoints))

                matchers.append(Matcher(name=f"{container.name}_read", rules=rules))

            # Write a request matcher for all methods
            if write_label:
                writeable_endpoints = [
                    endpoint.lstrip("/").casefold()
                    for endpoint in write_label.split(" ")
                ]
                rules = [remote_ip_rule]

                if "all" not in writeable_endpoints:
                    rules.append("vars {endpoint} " + " ".join(writeable_endpoints))

                matchers.append(Matcher(name=f"{container.name}_write", rules=rules))

    with TemporaryDirectory() as tmpdir:
        template = Template(
            (Path(__file__).parent / "Caddyfile.template.txt").read_text()
        )
        caddyfile = Path(tmpdir) / "Caddyfile"
        caddyfile.write_text(
            template.render(
                matchers=matchers, port=port, fallback_status_code=fallback_status_code
            )
        )
        subprocess.run(["caddy", "fmt", "--overwrite", str(caddyfile)])

        if json:
            print(
                subprocess.check_output(
                    ["caddy", "adapt", "--config", str(caddyfile)]
                ).decode("utf-8")
            )
        else:
            print(caddyfile.read_text())


@app.callback()
def main(): ...


logger.remove()
logger.add(
    level="INFO",
    format="{time:YYYY/MM/DD HH:mm:ss.SS} {level}  {message}",
    sink=sys.stderr,
)
logger.level("WARNING", color="<yellow>")

if __name__ == "__main__":
    app()
