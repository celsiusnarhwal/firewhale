# Firewhale

Firewhale is a proxy for the Docker socket.

## Why?

Giving a service direct access to your Docker socket
is [equivalent to giving it root access on your host](https://docs.docker.com/engine/security/#docker-daemon-attack-surface).
However, some services require access to the Docker socket for various reasons. Using this proxy allows you to grant
limited, per-service, access to the Docker socket, allowing you to control what individual services can and cannot
see and do.

> [!NOTE]
> Firewhale is designed to be used with other Docker containers. If you need a proxy for use with non-containerized
> services, see [Tecnativa/docker-socket-proxy](https://github.com/tecnativa/docker-socket-proxy).

> [!WARNING]
> Do you use [Watchtower](https://containrrr.dev/watchtower)? [Read this](#a-note-on-watchtower)
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

Firewhale will be accessible from services with which it shares a network at `http://firewhale:2375`.

> [!IMPORTANT]
> Firewhale only works with services it shares a network with.

A service's access to the Docker socket can be controlled with labels. The `firewhale.read` label controls
which Docker API endpoints a service can read from (i.e., send `GET` and `HEAD` requests to) and the `firewhale.write`
label controls which endpoints a service can write to
(i.e., additonally send `POST`, `PUT`, `PATCH`, and `DELETE` requests to). The value of each label should be a
space-separated list of
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
    DOCKER_HOST: http://firewhale:2375
  labels:
    firewhale.read: containers images networks volumes
    firewhale.write: containers images
```

In this example, `foobar` has read access to the `containers`, `images`, `networks`, and `volumes` endpoints
and write access to `containers` and `images`.

You can find an exhaustive list of endpoints in
the [Docker Engine API documentation](https://docs.docker.com/engine/api/version-history/).

> [!TIP]
> Firewhale accepts endpoint names both with and without a leading forward slash (e.g., `containers` and `/containers`
> are both valid).

### The `all` value

Both the `firewhale.read` and `firewhale.write` labels accept a special value called `all`. `all` grants
unrestricted read or write access to the Docker socket and is equivalent to specifying each endpoint individually.

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
    DOCKER_HOST: http://firewhale:2375
  labels:
    firewhale.read: all
    firewhale.write: containers images
```

In this example, `foobar` has read access to all endpoints and write access
to `containers` and `images`.

> [!IMPORTANT]
> Read access to the [`events`](https://docs.docker.com/engine/api/v1.45/#tag/System/operation/SystemEvents),
> [`_ping`](https://docs.docker.com/engine/api/v1.45/#tag/System/operation/SystemPing), and
> [`version`](https://docs.docker.com/engine/api/v1.45/#tag/System/operation/SystemVersion) endpoints is always granted,
> whether or not you do so explicitly. The information returned by these endpoints is practically harmless, and most
> services that hook into the Docker socket require these endpoints at a minimum.

## How It Works

Firewhale uses [Caddy](https://caddyserver.com) as its reverse proxy and dynamically generates
a [Caddyfile](https://caddyserver.com/docs/caddyfile) from your services'
`firewhale.read` and `firewhale.write` labels.

You can see the Caddyfile Firewhale is currently using at any time:

```shell
docker exec firewhale firewhale generate
```

You can also view the configuration in Caddy's canonical JSON:

```shell
docker exec firewhale firewhale generate --json
```

The JSON output produced by this command is always minified. You can prettify it
by piping it to [jq](https://jqlang.github.io/jq/) or a similar program.

## Configuration

Some aspects of Firewhale can be configured via environment variables.

| **Environment Variable**     | **Description**                                                                                                                                                                                                                                                                                 | **Default** |
|------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| `FIREWHALE_PORT`             | The port Firewhale should listen on. Firewhale will be accessible at `http://firewhale:${FIREWHALE_PORT}`. Must be an integer between 0 and 65535.                                                                                                                                              | 2375        |
| `FIREWHALE_HTTP_STATUS_CODE` | The [HTTP status code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status) Firewhale should respond with when it receives a request it has not been configured to allow. Must be an integer between 100 and 699.                                                                          | 403         |
| `FIREWHALE_REFRESH_INTERVAL` | The interval at which Firewhale will query Docker for any changes to your services' labels and update its rules accordingly. May be any [Go-style duration string](https://pkg.go.dev/time#ParseDuration), except you can also use `d` for day, `w` for week, `mm` for month, and `y` for year. | `30s`       |
| `FIREWHALE_LABEL_PREFIX`     | The prefix with which Firewhale labels should begin. Socket access will be configurable using the `${LABEL_PREFIX}.read` and `${LABEL_PREFIX}.write` labels.                                                                                                                                    | `firewhale` |

## A note on Watchtower

If you use [Watchtower](https://containrrr.dev/watchtower), it's important to make sure that either:

- a) Watchtower does _not_ use Firewhale as its Docker daemon socket, or
- b) Firewhale is exempted from Watchtower's update routine.

If Watchtower tries to update Firewhale while using it as its Docker daemon socket, it will lose access to the Docker
API after stopping Firewhale and will not be able to complete its update routine. Naturally, this will break anything
depending on Firewhale and any other containers Watchtower stopped during the update routine will be left as such.

See [Watchtower's documentation](https://containrrr.dev/watchtower/container-selection) for more info.

## Available Tags

| **Name**             | **Description**                                                                                        | **Example**                                                                            |
| -------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| `latest`             | The latest stable version of Firewhale.                                                                | `ghcr.io/celsiusnarhwal/firewhale:latest`                                              |
| Major version number | The latest version of Firewhale with this major version number. May be optionally prefixed with a `v`. | `ghcr.io/celsiusnarhwal/firewhale:1`<br/>`ghcr.io/celsiusnarhwal/firewhale:v1`         |
| Exact version number | This version of Firewhale exactly. May be optionally prefixed with a `v`.                              | `ghcr.io/celsiusnarhwal/firewhale:1.0.0`<br/>`ghcr.io/celsiusnarhwal/firewhale:v1.0.0` |
| `head`               | The latest commit to Firewhale's `main` branch. Unstable.                                              | `ghcr.io/celsiusnarhwal/firewhale:head`                                                |
