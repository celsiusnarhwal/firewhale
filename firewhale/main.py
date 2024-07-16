import os
import subprocess
import sys
import time
import typing as t
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

import httpx
import typer
from docker import DockerClient
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from firewhale.settings import FirewhaleSettings

settings = FirewhaleSettings()

jinja = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    trim_blocks=True,
    lstrip_blocks=True,
)

app = typer.Typer(
    no_args_is_help=True, add_completion=False, pretty_exceptions_show_locals=False
)


@app.command("generate")
def generate():
    """
    Generate a Caddy configuration for Firewhale.
    """

    class Matcher(t.TypedDict):
        name: str
        rules: list

    if settings.dev_mode:
        dc = DockerClient(**settings.dev_docker_opts)
    else:
        dc = DockerClient("unix:///var/run/docker.sock")

    matchers = []

    for container in dc.containers.list():
        read_label = container.labels.get(f"{settings.label_prefix}.read")
        write_label = container.labels.get(f"{settings.label_prefix}.write")

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

            # Write a request matcher for other readable endpoints
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

    template = jinja.get_template("Caddyfile.template.txt")
    caddyfile = template.render(matchers=matchers, settings=settings)

    print(caddyfile)

    return caddyfile


@app.command("start", hidden=True, add_help_option=False)
def _start():
    """
    Start Firewhale.
    """

    logger.info(f"Listening on port {settings.port}")
    logger.info(
        f"Reloading configuration every {settings.reload_interval_seconds} seconds"
    )

    subprocess.run(["caddy", "start"])

    first_reload_done = False

    while True:
        api_port = settings.caddy_api_port if first_reload_done else 2019

        with redirect_stdout(open(os.devnull, "w")):
            httpx.post(
                f"http://localhost:{api_port}/load",
                headers={"Content-Type": "text/caddyfile"},
                content=generate(),
            )

        first_reload_done = True

        time.sleep(settings.reload_interval_seconds)


@app.callback(
    epilog=f"© {datetime.now().astimezone().year} celsius narhwal. Thank you kindly for your attention."
)
def main():
    """
    Firewhale is a proxy for the Docker socket.
    """


logger.remove()
logger.add(
    level="INFO",
    format="{time:YYYY/MM/DD HH:mm:ss.SSS} {level}    firewhale   {message}",
    sink=sys.stderr,
)

if __name__ == "__main__":
    app()
