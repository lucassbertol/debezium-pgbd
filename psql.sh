#!/usr/bin/env bash
# Abre o psql da origem ou do destino no ambiente criado por iniciar-web.sh.
# Uso: ./psql.sh origem   ou   ./psql.sh destino
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "${1:-}" in
    origem|destino) ;;
    *) echo "Uso: $0 origem|destino" >&2; exit 2 ;;
esac
exec docker compose -p debezium-pgbd-demo-vazia -f compose.yaml -f compose.demo.yaml \
    exec "$1" psql -U postgres -d catalogo
