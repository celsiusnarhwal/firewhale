# Firewhale

Firewhale is a proxy for the Docker socket.

## Why?

Giving a service access to your Docker socket
is [equivalent to giving it root access on your host](https://docs.docker.com/engine/security/#docker-daemon-attack-surface).
However, some services require access to the Docker socket for various reasons. Using this proxy allows you to grant
limited, per-service, access to the Docker socket, allowing you to control what individual services can and cannot
see and do.

> [!NOTE]
> Firewhale is designed to be used with other Docker containers. If you need a proxy for use with non-containerized
> services, see [Tecnativa/docker-socket-proxy](https://github.com/tecnativa/docker-socket-proxy).

> [!WARNING]
> Do you use [Watchtower](https://containarrr.dev/watchtower)? [Read this](#a-note-on-watchtower) 
> before using Firewhale.

## Usage

Firewhale is designed to be used with [Docker Compose](https://docs.docker.com/compose/).

```yaml
services:
  firewhale:
    image: ghcr.io/celsiusnarhwal/firewhale
    container_name: firewhale
    restart: unless-stopped
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
```

Firewhale will be accessible from containers with which it shares a network at `http://firewhale:2375`.

A service's access to the Docker socket can be controlled with labels. The `firewhale.read` label controls
which Docker API endpoints a service can read from (i.e., send `GET` and `HEAD` requests to) and the `firewhale.write`
label controls which Docker API endpoints a service can write to
(i.e., additonally send `POST`, `PUT`, `PATCH`, and `DELETE` requests to). The value of each label should be a space-separated list of
endpoints the service should be able to read or write to.

Take a look at this example:

```yaml
services:
  firewhale:
    image: ghcr.io/celsiusnarhwal/firewhale
    container_name: firewhale
    restart: unless-stopped
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock

  foobar:
    image: foo/bar
    container_name: foobar
    restart: unless-stopped
  environment:
    - DOCKER_HOST=http://firewhale:2375
  labels:
    firewhale.read: containers images networks volumes
    firewhale.write: containers images
```

In this example, `foobar` has read access to the `containers`, `images`, `networks`, and `volumes` endpoints
and write access to `containers` and `images`.

> [!IMPORTANT]
> Only services with either or both of the `firewhale.read` and `firewhale.write` labels can access the Docker socket
> through Firewhale.

> [!TIP]
> Services can implicitly read from any endpoints that they can also write to.

### The `all` value

Both the `firewhale.read` and `firewhale.write` labels accept a special value called `all`. `all` grants
unrestricted read or write access to the Docker socket and is a shortcut for specifying each endpoint individually.

Iterating on the previous example:

```yaml
services:
  firewhale:
    image: ghcr.io/celsiusnarhwal/firewhale
    container_name: firewhale
    restart: unless-stopped
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock

  foobar:
    image: foo/bar
    container_name: foobar
    restart: unless-stopped
  environment:
    - DOCKER_HOST=http://firewhale:2375
  labels:
    firewhale.read: all
    firewhale.write: containers images
```

In this example, `foobar` has read access to all endpoints and write access
to `containers` and `images`.

> [!TIP]
> Configuring a service to use Firewhale means making it use Firewhale as its Docker daemon socket. 
> If the service's documentation doesn't tell you how to do this, setting the `DOCKER_HOST` environment variable will usually do the trick.

> [!IMPORTANT]
> Read access to the `events`, `ping`, and `version` endpoints is always granted, whether or not you do so explicitly.
> The information returned by these endpoints is mostly harmless, and most services that hook into the Docker socket
> require these endpoints at a minimum.

## How It Works

Firewhale uses [Caddy](https://caddyserver.com) as its reverse proxy and dynamically generates
a [Caddyfile](https://caddyserver.com/docs/caddyfile)
from your services' `firewhale.read` and `firewhale.write`.
The [`remote_ip`](https://caddyserver.com/docs/caddyfile/matchers#remote-ip)
request matcher allows Firewhale to support different levels of access for each service.

You can see the Caddyfile Firewhale is currently using at any time:

```shell
docker exec firewhale firewhale generate
```

You can also view the configuration in Caddy's canonical JSON:

```shell
docker exec firewhale firewhale generate --json
```

The JSON output produced this command is always minified. You can prettify it
by piping it to [jq](https://jqlang.github.io/jq/) or a similar program.

## Configuration

Some aspects of Firewhale can be configured via environment variables.

| **Environment Variable**     | **Description**                                                                                                                                                                                                             | **Default** |
|------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| `FIREWHALE_PORT`             | The port Firewhale should listen on. Firewhale will be accessible at `https://firewhale:${FIREWHALE_PORT}`. Must be an integer between 0 and 65535.                                                                         | 2375        |
| `FIREWHALE_HTTP_STATUS_CODE` | The [HTTP status code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status) Firewhale should respond with when it receives a request that it has not been configured to allow. Must be an integer between 100 and 699. | 403         |
| `FIREWHALE_REFRESH_INTERVAL` | The interval, in seconds, at which Firewhale will query Docker for any updates to your services' labels and update its rules accordingly.                                                                                   | 30          |
| `FIREWHALE_LABEL_PREFIX`     | The prefix which with Firewhale labels will begin. Socket access will be configurable using the `${LABEL_PREFIX}.read` and `${LABEL_PREFIX}.write` labels.                                                                  | `firewhale` |

Firewhale uses Docker's [official Python SDK](https://github.com/docker/docker-py) and will thus honor the
`DOCKER_HOST`, `DOCKER_TLS_VERIFY`, and `DOCKER_CERT_PATH` environment variables if they are set.

## A note on Watchtower

If you use [Watchtower](https://containrrr.dev/watchtower), it's important to make sure that either:

- a) Watchtower does _not_ use Firewhale as its Docker daemon socket, or
- b) Firewhale is exempted from Watchtower's update routine.

If Watchtower tries to update Firewhale while using it as its Docker daemon socket, it will lose access to the Docker
API after stopping Firewhale and will not be able to complete its update routine. Naturally, this will break anything
depending on Firewhale and any other containers Watchtower stopped during the update routine will be left as such.

See [Watchtower's documentation](https://containrrr.dev/watchtower/container-selection/#monitor_only) for more.