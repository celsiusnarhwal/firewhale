FROM ghcr.io/astral-sh/uv:0.7-debian

ENV PATH=/app/.venv/bin:${PATH}

COPY --from=caddy:2.8.4 /usr/bin/caddy /usr/bin/caddy

WORKDIR /app/

COPY . /app/
RUN uv sync

HEALTHCHECK CMD curl -f localhost:${FIREWHALE_CADDY_API_PORT:-2019}/config/

CMD ["firewhale", "start"]