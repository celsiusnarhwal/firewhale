import os
import subprocess
import time
from datetime import datetime

import httpx
import typer
from loguru import logger

from firewhale import _internal
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

    logger.debug("Starting Caddy")

    subprocess.run(
        ["caddy", "start"],
        env={**os.environ, "CADDY_ADMIN": settings.caddy_admin_address},
    )

    while True:
        logger.debug(
            f"Updating Caddy configuration via admin API at {settings.caddy_admin_address}"
        )

        try:
            resp = httpx.post(
                f"http://{settings.caddy_admin_address}/load",
                headers={"Content-Type": "text/caddyfile"},
                content=_internal.generate(),
            )
        except httpx.ConnectError:
            logger.error(
                f"There was an error communicating with Caddy's admin API at {settings.caddy_admin_address}. "
                f"Please restart Firewhale."
            )
        else:
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                logger.error(
                    f"Firewhale received an unexpected status code "
                    f"({resp.status_code} {httpx.codes.get_reason_phrase(resp.status_code)}) while communicating with "
                    f"Caddy's admin API. Please restart Firewhale."
                )

        time.sleep(settings.reload_interval_seconds)
        logger.info("Reloading configuration")


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
