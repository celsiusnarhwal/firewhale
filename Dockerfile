FROM caddy:2.8.4-builder AS caddy

RUN xcaddy build --with github.com/muety/caddy-remote-host

FROM python:3.12.1

ENV PIPX_BIN_DIR=/opt/pipx
ENV PATH=${PATH}:${PIPX_BIN_DIR}

COPY --from=caddy /usr/bin/caddy /usr/bin/caddy

WORKDIR /app/

RUN curl -fsSL https://github.com/pypa/pipx/releases/latest/download/pipx.pyz | install /dev/stdin /usr/local/bin/pipx

COPY .poetry-version /app/
RUN pipx install poetry==$(cat .poetry-version) && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock /app/
RUN poetry install --no-root --only main

COPY . /app/
RUN poetry install --only-root

HEALTHCHECK CMD curl -f localhost:${FIREWHALE_CADDY_API_PORT:-2019}/config/

CMD ["firewhale", "start"]