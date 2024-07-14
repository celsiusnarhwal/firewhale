#!/bin/sh

caddy start

while true; do
  curl -s localhost:2019/load -H "Content-Type:application/json" -d $(firewhale generate --json)
  sleep ${FIREWHALE_REFRESH_INTERVAL:-30}
done