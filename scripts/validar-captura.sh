#!/usr/bin/env bash
set -euo pipefail

sql() {
    docker compose exec -T origem psql -XqAt -v ON_ERROR_STOP=1 -U postgres -d catalogo -c "$1"
}

[[ "$(sql 'SHOW wal_level')" == logical ]]
[[ "$(sql "SELECT rolcanlogin AND rolreplication
    AND has_database_privilege(rolname, current_database(), 'CONNECT')
    AND has_table_privilege(rolname, 'public.produtos', 'SELECT')
    FROM pg_roles WHERE rolname = 'cdc'")" == t ]]
[[ "$(sql "SELECT count(*) FROM pg_publication_tables
    WHERE pubname = 'produtos_publicacao' AND schemaname = 'public' AND tablename = 'produtos'")" == 1 ]]
[[ "$(sql "SELECT count(*) FROM pg_replication_slots
    WHERE slot_name = 'produtos_slot' AND plugin = 'pgoutput'
    AND database = current_database() AND active")" == 1 ]]

curl --fail --silent --show-error http://127.0.0.1:8083/connectors/produtos-origem/status |
    python3 -c 'import json, sys; s = json.load(sys.stdin); assert s["connector"]["state"] == "RUNNING" and len(s["tasks"]) == 1 and s["tasks"][0]["state"] == "RUNNING", s'

# A chave reservada para a verificação muda a cada execução.
id="$(sql "INSERT INTO public.produtos (id, nome, estoque)
    VALUES (-(100000000 + floor(random() * 1000000000)::integer), 'Validação CDC', 10)
    RETURNING id")"
sql "UPDATE public.produtos SET estoque = 7 WHERE id = $id"
sql "DELETE FROM public.produtos WHERE id = $id"

docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 --topic catalogo.public.produtos --from-beginning \
    --timeout-ms 8000 --property print.key=true |
    python3 -c '
import json
import sys

product_id = int(sys.argv[1])
expected = [("c", 10), ("u", 7), ("d", None)]
observed = []
for line in sys.stdin:
    key, value = map(json.loads, line.split("\t", 1))
    if not key or key["payload"]["id"] != product_id or value is None:
        continue
    event = value["payload"]
    if event["op"] == "r":
        continue
    stock = event["after"]["estoque"] if event["after"] else None
    observed.append((event["op"], stock))
    print(f"id={product_id} op={event['"'"'op'"'"']} estoque={stock}")

assert observed == expected, f"Esperado: {expected}. Observado: {observed}"
' "$id"
