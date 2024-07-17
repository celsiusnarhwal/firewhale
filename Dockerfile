FROM caddy:2.8.4-builder AS caddy

RUN xcaddy build --with github.com/muety/caddy-remote-host

FROM python:3.12.1

LABEL org.opencontainers.image.source=https://github.com/celsiusnarhwal/firewhale

ENV PIPX_BIN_DIR=/opt/pipx
ENV PATH=${PATH}:${PIPX_BIN_DIR}

COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
COPY .poetry-version /app/

WORKDIR /app

RUN pip install pipx \
    && pipx install poetry==$(cat .poetry-version) \
    && poetry config virtualenvs.create false

COPY . /app/

RUN poetry install --only main

CMD ["firewhale", "start"]