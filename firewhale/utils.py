from docker import DockerClient
from loguru import logger

from firewhale.settings import settings


def get_docker_client() -> DockerClient:
    if settings().dev_mode and settings().dev_docker_opts:
        dc = DockerClient(**settings().dev_docker_opts)
    else:
        dc = DockerClient("unix:///var/run/docker.sock")

    logger.debug("Connected to Docker Engine")

    return dc
