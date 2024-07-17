FROM caddy:2.8.4-builder AS caddy

RUN xcaddy build --with github.com/muety/caddy-remote-host

FROM python:3.12.1

ENV PIPX_BIN_DIR=/opt/pipx
ENV PATH=${PATH}:${PIPX_BIN_DIR}

COPY --from=caddy /usr/bin/caddy /usr/bin/caddy

RUN curl -fsSL https://github.com/pypa/pipx/releases/latest/download/pipx.pyz -o pipx.pyz

RUN --mount=type=bind,source=.poetry-version,target=.poetry-version \
    python pipx.pyz install poetry==$(cat .poetry-version) && poetry config virtualenvs.create false

WORKDIR /app/

COPY pyproject.toml poetry.lock /app/
RUN poetry install --no-root --only main

COPY . /app/
RUN poetry install --only-root

CMD ["firewhale", "start"]

LABEL org.opencontainers.image.source=https://github.com/celsiusnarhwal/firewhale
