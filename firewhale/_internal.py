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

    matchers = []

    for container in dc.containers.list():
        read_label = container.labels.get(f"{settings.label_prefix}.read")
        write_label = container.labels.get(f"{settings.label_prefix}.write")

        # Write a request matcher for read access to /events, /_ping, and /version
        if read_label or write_label:
            remote_host_rule = f"remote_host {container.name}"

            matchers.append(
                Matcher(
                    name=f"{container.name}_basic",
                    rules=[
                        remote_host_rule,
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
                rules = [remote_host_rule, "method GET HEAD"]

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

    return caddyfile
