import os
import subprocess
import sys
import typing as t
from pathlib import Path
from tempfile import TemporaryDirectory

import durationpy
import typer
from docker import DockerClient
from jinja2 import Template
from datetime import datetime
from loguru import logger
from pydantic import Field, TypeAdapter, ValidationError


class Matcher(t.TypedDict):
    name: str
    rules: list


HERE = Path(__file__).parent

app = typer.Typer(no_args_is_help=True, add_completion=False)

@app.command("generate", help="Generate a Caddy configuration for Firewhale.")
def generate(
    json: bool = typer.Option(
        False, "--json", help="Generate a JSON configuration instead of a Caddyfile."
    )
):
    dc = DockerClient("unix://var/run/docker.sock")

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

    for container in dc.containers.list():
        read_label = container.labels.get(f"{label_prefix}.read")
        write_label = container.labels.get(f"{label_prefix}.write")

        # Write a request matcher for read access to /events, /_ping, and /version
        if read_label or write_label:
            matchers.append(
                Matcher(
                    name=f"{container.name}_basic",
                    rules=[
                        f"remote_host {container.name}",
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
                rules = [f"remote_host {container.name}", "method GET HEAD"]

                if "all" not in readable_endpoints:
                    rules.append("vars {endpoint} " + " ".join(readable_endpoints))

                matchers.append(Matcher(name=f"{container.name}_read", rules=rules))

            # Write a request matcher for all methods
            if write_label:
                writeable_endpoints = [
                    endpoint.lstrip("/").casefold()
                    for endpoint in write_label.split(" ")
                ]
                rules = [f"remote_host {container.name}"]

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


@app.command("duration", hidden=True)
def duration(d: str):
    try:
        print(durationpy.from_str(d).total_seconds())
    except ValueError:
        raise ValueError(
            "FIREWHALE_REFRESH_INTERVAL must be a valid Go-style duration string. "
            "https://pkg.go.dev/time#ParseDuration"
        ) from None


@app.callback(epilog=f"© {datetime.now().astimezone().year} celsius narhwal. Thank you kindly for your attention.")
def main():
    """
    Firewhale is a proxy for the Docker socket.
    """


logger.remove()
logger.add(
    level="INFO",
    format="{time:YYYY/MM/DD HH:mm:ss.SS} {level}  {message}",
    sink=sys.stderr,
)
logger.level("WARNING", color="<yellow>")

if __name__ == "__main__":
    app()
