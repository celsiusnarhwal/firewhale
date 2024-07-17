# Firewhale

Firewhale is a proxy for the Docker socket.

<hr>

<details>
<summary>Supported Tags</summary>
<br>

| **Name**             | **Description**                                                                                        | **Example**                                                                            |
|----------------------|--------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| `latest`             | The latest stable version of Firewhale.                                                                | `ghcr.io/celsiusnarhwal/firewhale:latest`                                              |
| Major version number | The latest version of Firewhale with this major version number. May be optionally prefixed with a `v`. | `ghcr.io/celsiusnarhwal/firewhale:1`<br/>`ghcr.io/celsiusnarhwal/firewhale:v1`         |
| Exact version number | This version of Firewhale exactly. May be optionally prefixed with a `v`.                              | `ghcr.io/celsiusnarhwal/firewhale:1.0.0`<br/>`ghcr.io/celsiusnarhwal/firewhale:v1.0.0` |
| `head`               | The latest commit to Firewhale's `main` branch. Unstable.                                              | `ghcr.io/celsiusnarhwal/firewhale:head`                                                |

</details>

<details>
<summary>Supported Architectures</summary>
<br>

- `amd64`
- `arm64`

</details>

<hr>

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

## How?

Firewhale is built on top of [Caddy](https://caddyserver.com)
and dynamically generates a [Caddyfile](https://caddyserver.com/docs/caddyfile) using Docker service labels.

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

By default, Firewhale will be accessible from services with which it shares a network at `http://firewhale:2375`.

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
    depends_on:
      - firewhale
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
    depends_on:
      - firewhale
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

## Interacting with Firewhale

### Viewing the Caddyfile

You can view the Caddyfile Firewhale is currently using with `firewhale view`.

```shell
docker exec firewhale firewhale view
```

### Using the Caddy API

By default, Caddy's [admin API](https://caddyserver.com/docs/api) is available inside Firewhale's container at
`localhost:2019`.

```shell
docker exec firewhale curl -s localhost:2019
```

> [!WARNING]
> Any configuration changes made via the admin API will be lost when Firewhale's container is restarted or recreated.

## Docker API Compatibility

Firewhale supports all versions of the Docker API that are also supported by Docker's
[official Python SDK](https://github.com/docker/docker-py).

## Configuration

Some aspects of Firewhale can be configured via environment variables.

| **Environment Variable**     | **Description**                                                                                                                                                                                                                                                                                               | **Default** |
|------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| `FIREWHALE_PORT`             | The port on which Firewhale should listen. Firewhale will be accessible at `http://firewhale:${FIREWHALE_PORT}`. Must be an integer between 0 and 65535 and different than `FIREWHALE_CADDY_API_PORT`.                                                                                                        | 2375        |
| `FIREWHALE_CADDY_API_PORT`   | The port on which Caddy's [admin API](https://caddyserver.com/docs/api) should listen. The Caddy API will be accessible at `localhost:${FIREWHALE_CADDY_API_PORT}` within Firewhale's container. Must be an integer between 0 and 65535 and different than `FIREWHALE_PORT`.                                  | 2019        |
| `FIREWHALE_HTTP_STATUS_CODE` | The [HTTP status code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status) Firewhale should respond with when it receives a request it has not been configured to allow. Must be an integer between 100 and 599.                                                                                        | 403         |
| `FIREWHALE_RELOAD_INTERVAL`  | The interval at which Firewhale will query Docker for any changes to your services' labels and update its rules accordingly. Must be in the format of a [Go duration string](https://pkg.go.dev/time#ParseDuration), except you can also use `d` for day, `w` for week, `mm` for month, and `y` for year.[^1] | `30s`       |
| `FIREWHALE_LABEL_PREFIX`     | The prefix with which Firewhale labels should begin. Socket access will be configurable using the `${LABEL_PREFIX}.read` and `${LABEL_PREFIX}.write` labels.                                                                                                                                                  | `firewhale` |

## Considerations

- Firewhale only works on [user-defined bridge networks](https://docs.docker.com/network/drivers/bridge/#differences-between-user-defined-bridges-and-the-default-bridge).
  This shouldn't be an issue if you're using Docker Compose, where such networks are the default for services that aren't explicitly defined to use something else.
  But just to be clear, you can't use Docker's predefined bridge network or the host or Macvlan networking drivers with Firewhale.
- Firewhale can only communicate over plain HTTP. TLS connections aren't supported and aren't planned to be.
- Firewhale does _not_ honor the following environment variables and setting them will have no effect:
  - `DOCKER_HOST`
  - `DOCKER_TLS_VERIFY`
  - `DOCKER_CERT_PATH`
  - `CADDY_ADMIN`

### A note on Watchtower

If you use [Watchtower](https://containrrr.dev/watchtower), it's important to make sure that either:

- a) Watchtower does _not_ use Firewhale as its Docker daemon socket, or
- b) Firewhale is exempted from Watchtower's update routine.

If Watchtower tries to update Firewhale while using it as its Docker daemon socket, it will lose access to the Docker
API after stopping Firewhale and will not be able to complete its update routine. Naturally, this will break anything
depending on Firewhale and any other containers Watchtower stopped during the update routine will be left as such.

See [Watchtower's documentation](https://containrrr.dev/watchtower/container-selection) for more info.

[^1]: 1 day = 24 hours, 1 week = 7 days, 1 month = 30 days, and 1 year = 365 days.