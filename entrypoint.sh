#!/bin/sh

caddy start

while true; do
  curl localhost:2019/load -H "Content-Type:application/json" -d $(firewhale generate --json)
  sleep ${FIREWHALE_REFRESH_INTERVAL:-30}
done