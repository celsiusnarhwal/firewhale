FROM caddy:2.8.4-builder AS caddy

RUN xcaddy build --with github.com/muety/caddy-remote-host

FROM ghcr.io/astral-sh/uv:0.5-debian

ENV PATH=/app/.venv/bin:${PATH}

COPY --from=caddy /usr/bin/caddy /usr/bin/caddy

WORKDIR /app/

COPY pyproject.toml uv.lock README.md /app/
RUN uv sync

COPY . /app/

HEALTHCHECK CMD curl -f localhost:${FIREWHALE_CADDY_API_PORT:-2019}/config/

CMD ["firewhale", "start"]