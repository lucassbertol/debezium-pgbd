#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
compose=(docker compose -p debezium-pgbd-demo-vazia -f compose.yaml -f compose.demo.yaml)

echo "Recriando o ambiente descartável de demonstração com dados vazios."
"${compose[@]}" down --volumes
"${compose[@]}" up -d --build --wait --wait-timeout 180
"${compose[@]}" exec -T web python /demo/inicializar.py
echo "Abra http://127.0.0.1:18000/"
