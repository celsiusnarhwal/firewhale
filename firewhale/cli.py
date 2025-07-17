import os
import subprocess
from datetime import datetime

import typer
from loguru import logger

from firewhale import _internal, utils
from firewhale.settings import FirewhaleSettings
from firewhale.types import LogLevel

settings = FirewhaleSettings()

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=True,
    help="Firewhale is a proxy for the Docker socket.",
    epilog=f"© {datetime.now().astimezone().year} celsius narhwal. Thank you kindly for your attention.",
)


@app.command("view")
def view():
    """
    View Firewhale's current Caddyfile.
    """
    print(_internal.generate_caddyfile())


@app.command("start", hidden=True, add_help_option=False)
def _start():
    """
    Start Firewhale.
    """
    logger.info(f"Listening on port {settings.port}")
    logger.info(
        f"Reloading configuration every {settings.reload_interval_seconds} seconds"
    )

    logger.debug("Starting Caddy")

    subprocess.run(
        ["caddy", "start"],
        env={**os.environ, "CADDY_ADMIN": settings.caddy_admin_address},
    )

    dc = utils.get_docker_client()

    for event in dc.events(decode=True):
        if event.get("Type") == "container" and event.get("Action") in [
            "start",
            "stop",
        ]:
            print(event)
            caddyfile = _internal.generate_caddyfile()
            _internal.apply_caddyfile(caddyfile)


@app.callback()
def main():
    logger.remove()
    logger.add(
        level="WARNING" if settings.log_level is LogLevel.WARN else settings.log_level,
        sink=_internal.log_sink,
        serialize=True,
    )


if __name__ == "__main__":
    app()
