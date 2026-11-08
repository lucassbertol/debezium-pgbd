import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CONNECT = "http://connect:8083/connectors"
WEB = "http://127.0.0.1:8000/api"


def read_json(url):
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def wait_for(url, ready, description):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            value = read_json(url)
        except HTTPError as exc:
            if exc.code not in (404, 503):
                raise
        else:
            if ready(value):
                return value
        time.sleep(1)
    raise SystemExit(f"Tempo esgotado ao aguardar {description}.")


def connector_running(status):
    states = [status["connector"]["state"], *(task["state"] for task in status["tasks"])]
    if "FAILED" in states:
        raise SystemExit("Um conector falhou. Consulte os logs do serviço connect.")
    return len(states) > 1 and all(state == "RUNNING" for state in states)


for role in ("origem", "destino"):
    url = f"{CONNECT}/produtos-{role}"
    config = Path(f"/demo/connect/{role}.json").read_bytes()
    request = Request(
        f"{url}/config",
        data=config,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urlopen(request, timeout=30):
        pass
    wait_for(f"{url}/status", connector_running, f"conector de {role} em RUNNING")
    print(f"Conector de {role} em execução.", flush=True)

for path in ("produtos/origem", "produtos/destino", "eventos"):
    rows = wait_for(f"{WEB}/{path}", lambda value: isinstance(value, list), path)
    if rows:
        raise SystemExit(f"O painel {path} não iniciou vazio.")

print("Bancos de origem e destino e painel de eventos vazios.")
