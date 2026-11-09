"""Teste do cronômetro com Playwright. Execute na raiz do projeto."""
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

STATIC = Path("web/static")
product = {"id": 102, "nome": "Caneta", "estoque": 10}
catalog = [{"id": 101, "nome": "Caderno", "estoque": 7}, product]
events = []
destination = []
source_status = {"connector": "RUNNING", "tasks": ["RUNNING"]}


def add_event(operation, timestamp, commit=None):
    """commit simula source.ts_ms; sem ele, o cronômetro usa ts_ms."""
    payload = {"ts_ms": timestamp, "after": product if operation != "d" else None}
    if commit is not None:
        payload["source"] = {"ts_ms": commit}
    events.insert(0, {
        "partition": 0, "offset": len(events), "id": product["id"], "op": operation,
        "value": {"payload": payload},
    })


def respond(route):
    path = urlsplit(route.request.url).path
    if path == "/":
        return route.fulfill(path=STATIC / "index.html")
    if path.startswith("/static/"):
        return route.fulfill(path=STATIC / path.rsplit("/", 1)[1])
    if path.startswith("/api/produtos/origem/"):
        product_id = int(path.rsplit("/", 1)[1])
        row = next(row for row in catalog if row["id"] == product_id)
        if route.request.method == "PATCH":
            row.update(route.request.post_data_json)
        elif route.request.method == "DELETE":
            catalog.remove(row)
        else:
            return route.fulfill(status=405)
        return route.fulfill(json={"id": product_id})
    responses = {
        "/api/produtos/origem": catalog,
        "/api/produtos/destino": destination,
        "/api/eventos": events,
        "/api/source": source_status,
        "/api/sink": {"connector": "PAUSED", "tasks": ["PAUSED"]},
    }
    if path not in responses:
        return route.fulfill(status=404)
    route.fulfill(json=responses[path])


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.route("http://cdc.test/**", respond)
    add_event("c", int(time.time() * 1000) - 60_000)
    page.goto("http://cdc.test/")
    expect(page.get_by_role("table", name="Produtos na origem")).to_be_visible()
    expect(page.get_by_role("button", name="Consultar banco")).to_have_count(0)
    expect(page.locator("dialog")).to_have_count(0)

    status = page.locator("#replication-status")
    elapsed = page.locator("#replication-elapsed")
    expect(page.locator("#events-data")).to_contain_text("ID 102")
    expect(page.locator("#source-state")).to_have_text("Em execução")
    expect(page.locator("#source-last-event")).to_contain_text("Inserção do produto 102")
    expect(page.locator("#sink-state")).to_have_text("Pausado")
    expect(page.locator("#sink-activity")).to_contain_text("Aplicação pausada")
    expect(status).to_have_text("Aguardando uma nova alteração no Kafka.")

    add_event("u", int(time.time() * 1000))
    destination[:] = [dict(product, estoque=7)]
    expect(status).to_have_text("Aguardando no destino: atualização do produto 102.")
    expect(elapsed).to_have_text(re.compile(r"^(?!0,000 s$)\d+,\d{3} s$"))
    expect(status).to_have_text("Aguardando no destino: atualização do produto 102.")

    destination[:] = [product]
    expect(status).to_contain_text("Atualização do produto 102 confirmada no destino")
    final_time = elapsed.inner_text()
    page.wait_for_timeout(250)
    expect(elapsed).to_have_text(final_time)
    expect(page.locator("#destino-data")).to_contain_text("Caneta")
    expect(page.locator("#destino-data").get_by_role("button")).to_have_count(0)

    # A contagem começa no commit (source.ts_ms): um commit de 5 s atrás já aparece com pelo menos 5 s.
    now = int(time.time() * 1000)
    add_event("u", now, commit=now - 5000)
    destination[:] = [dict(product, estoque=3)]
    expect(status).to_have_text("Aguardando no destino: atualização do produto 102.")
    seconds = float(elapsed.inner_text().removesuffix(" s").replace(",", "."))
    assert seconds >= 5, seconds
    destination[:] = [product]
    expect(status).to_contain_text("confirmada no destino")

    add_event("d", int(time.time() * 1000))
    expect(status).to_have_text("Aguardando no destino: exclusão do produto 102.")
    destination.clear()
    expect(status).to_contain_text("Exclusão do produto 102 confirmada no destino")

    source_status["tasks"] = ["FAILED"]
    expect(page.locator("#source-state")).to_have_text("Falha")
    expect(page.locator("#source-activity")).to_contain_text("Falha no conector de captura")

    origin = page.get_by_role("table", name="Produtos na origem")
    origin.get_by_role("button", name="Editar produto 101").click()
    expect(page.get_by_label("ID", exact=True)).to_have_value("101")
    expect(page.get_by_label("Nome", exact=True)).to_have_value("Caderno")
    expect(page.get_by_label("Estoque", exact=True)).to_be_focused()
    page.get_by_label("Estoque", exact=True).fill("8")
    page.get_by_role("button", name="Salvar estoque").click()
    expect(origin.get_by_role("row", name="101 Caderno 8")).to_be_visible()
    expect(page.get_by_role("button", name="Inserir produto")).to_be_visible()
    page.once("dialog", lambda confirmation: confirmation.dismiss())
    origin.get_by_role("button", name="Excluir produto 101").click()
    expect(origin.get_by_role("row", name="101 Caderno 8")).to_be_visible()
    page.once("dialog", lambda confirmation: confirmation.accept())
    origin.get_by_role("button", name="Excluir produto 101").click()
    expect(origin.get_by_role("row", name="101 Caderno 8")).to_have_count(0)
