import os
import subprocess
import time
from datetime import datetime

import httpx
import typer
from loguru import logger

from firewhale import _internal
from firewhale.settings import FirewhaleSettings

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
    print(_internal.generate())


@app.command("start", hidden=True, add_help_option=False)
def _start():
    """
    Start Firewhale.
    """
    logger.info(f"Listening on port {settings.port}")
    logger.info(
        f"Reloading configuration every {settings.reload_interval_seconds} seconds"
    )

    subprocess.run(
        ["caddy", "start"],
        env={**os.environ, "CADDY_ADMIN": settings.caddy_admin_address},
    )

    while True:
        httpx.post(
            f"http://{settings.caddy_admin_address}/load",
            headers={"Content-Type": "text/caddyfile"},
            content=_internal.generate(),
        )

        time.sleep(settings.reload_interval_seconds)
        logger.info("Reloading configuration")


logger.remove()
logger.add(
    level="INFO",
    sink=_internal.log_sink,
    serialize=True,
)

if __name__ == "__main__":
    app()
