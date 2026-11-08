#!/usr/bin/env bash
set -euo pipefail

connect=http://127.0.0.1:8083/connectors

sql() {
    docker compose exec -T "$1" psql -XqAt -v ON_ERROR_STOP=1 \
        -U postgres -d catalogo -c "$2"
}

stock() {
    sql "$1" "SELECT estoque FROM public.produtos WHERE id = $2"
}

state() {
    curl -fsS "$connect/$1/status" | python3 -c '
import json, sys
status = json.load(sys.stdin)
states = [status["connector"]["state"]] + [task["state"] for task in status["tasks"]]
print(" ".join(states))
'
}

wait_for() {
    local expected="$1" actual
    shift
    for ((attempt = 0; attempt < 30; attempt++)); do
        actual="$("$@")"
        if [[ "$actual" == "$expected" ]]; then
            return
        fi
        sleep 1
    done
    printf 'Falha em %s: esperado [%s], observado [%s]\n' "$*" "$expected" "$actual" >&2
    return 1
}

insert_product() {
    sql origem "INSERT INTO public.produtos (id, nome, estoque)
        VALUES (-(100000000 + floor(random() * 1000000000)::integer), 'Validação sink', 10)
        RETURNING id"
}

wait_for 'RUNNING RUNNING' state produtos-origem
wait_for 'RUNNING RUNNING' state produtos-destino

id="$(insert_product)"
[[ "$(stock origem "$id")" == 10 ]]
wait_for 10 stock destino "$id"
printf 'INSERT id=%s origem=10 destino=10\n' "$id"

sql origem "UPDATE public.produtos SET estoque = 7 WHERE id = $id"
[[ "$(stock origem "$id")" == 7 ]]
wait_for 7 stock destino "$id"
printf 'UPDATE id=%s origem=7 destino=7\n' "$id"

sql origem "DELETE FROM public.produtos WHERE id = $id"
[[ -z "$(stock origem "$id")" ]]
wait_for '' stock destino "$id"
printf 'DELETE id=%s origem=ausente destino=ausente\n' "$id"

trap 'curl -fsS -X PUT "$connect/produtos-destino/resume" >/dev/null' EXIT
curl -fsS -X PUT "$connect/produtos-destino/pause" >/dev/null
wait_for 'PAUSED PAUSED' state produtos-destino
wait_for 'RUNNING RUNNING' state produtos-origem
paused_id="$(insert_product)"
[[ "$(stock origem "$paused_id")" == 10 ]]

docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 --topic catalogo.public.produtos --from-beginning \
    --timeout-ms 8000 --property print.key=true |
    python3 -c '
import json
import sys

first_id, paused_id = map(int, sys.argv[1:])
observed = {first_id: [], paused_id: []}
for line in sys.stdin:
    key, value = map(json.loads, line.split("\t", 1))
    if key is None or key["payload"]["id"] not in observed:
        continue
    product_id = key["payload"]["id"]
    operation = "tombstone" if value is None else value["payload"]["op"]
    observed[product_id].append(operation)
    print(f"Kafka id={product_id} evento={operation}")

assert observed == {first_id: ["c", "u", "d", "tombstone"], paused_id: ["c"]}, observed
' "$id" "$paused_id"

[[ "$(state produtos-destino)" == 'PAUSED PAUSED' ]]
[[ -z "$(stock destino "$paused_id")" ]]
printf 'PAUSED id=%s origem=10 destino=ausente\n' "$paused_id"

curl -fsS -X PUT "$connect/produtos-destino/resume" >/dev/null
wait_for 'RUNNING RUNNING' state produtos-destino
trap - EXIT
wait_for 10 stock destino "$paused_id"
printf 'RUNNING id=%s destino=10\n' "$paused_id"

sql origem "DELETE FROM public.produtos WHERE id = $paused_id"
wait_for '' stock destino "$paused_id"
