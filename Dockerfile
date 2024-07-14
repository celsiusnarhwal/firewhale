FROM caddy:2.8.4 AS caddy

FROM python:3.12.1

LABEL org.opencontainers.image.source=https://github.com/celsiusnarhwal/firewhale

ENV PIPX_BIN_DIR=/opt/pipx
ENV PATH=${PATH}:${PIPX_BIN_DIR}

COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
COPY . /app

WORKDIR /app

RUN apt upgrade \
		&& apt install pipx
    && pipx install poetry==$(cat .poetry-version) \
    && poetry config virtualenvs.create false \
    && poetry install --only main

CMD ["./entrypoint.sh"]