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


def add_event(operation, timestamp):
    events.insert(0, {
        "partition": 0, "offset": len(events), "id": product["id"], "op": operation,
        "value": {"payload": {"ts_ms": timestamp, "after": product if operation != "d" else None}},
    })


def respond(route):
    path = urlsplit(route.request.url).path
    if path == "/":
        return route.fulfill(path=STATIC / "index.html")
    if path.startswith("/static/"):
        return route.fulfill(path=STATIC / path.rsplit("/", 1)[1])
    if path.startswith("/api/consulta/"):
        bank = path.rsplit("/", 1)[1]
        return route.fulfill(json={
            "sql": "SELECT id, nome, estoque FROM public.produtos ORDER BY id;",
            "rows": catalog if bank == "origem" else destination,
        })
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
        "/api/produtos/origem": [],
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
    expect(page.locator("main table")).to_have_count(0)

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
    expect(status).to_contain_text("Atualização do produto 102 observada no destino")
    final_time = elapsed.inner_text()
    page.wait_for_timeout(250)
    expect(elapsed).to_have_text(final_time)

    add_event("d", int(time.time() * 1000))
    expect(status).to_have_text("Aguardando no destino: exclusão do produto 102.")
    destination.clear()
    expect(status).to_contain_text("Exclusão do produto 102 observada no destino")

    source_status["tasks"] = ["FAILED"]
    expect(page.locator("#source-state")).to_have_text("Falha")
    expect(page.locator("#source-activity")).to_contain_text("Falha no conector de captura")

    for bank, count in (("origem", "2 linhas retornadas."), ("destino", "0 linhas retornadas.")):
        title = f"Consultar banco de {bank}"
        button = page.get_by_role("button", name=title)
        button.click()
        dialog = page.get_by_role("dialog", name=title)
        expect(dialog.locator("#query-status")).to_have_text(count)
        dialog.get_by_text("SQL executado", exact=True).click()
        expect(dialog.locator("#query-sql")).to_contain_text("ORDER BY id;")
        if bank == "origem":
            expect(dialog.get_by_role("row", name="101 Caderno 7")).to_be_visible()
            expect(dialog.get_by_role("row", name="102 Caneta 10")).to_be_visible()
        else:
            destination[:] = catalog
            dialog.get_by_role("button", name="Atualizar visualização").click()
            expect(dialog.locator("#query-status")).to_have_text("2 linhas retornadas.")
            expect(dialog.get_by_role("button", name="Editar produto 101")).to_have_count(0)
            expect(dialog.get_by_role("button", name="Excluir produto 101")).to_have_count(0)
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(button).to_be_focused()

    page.on("dialog", lambda confirmation: confirmation.accept())
    page.get_by_role("button", name="Consultar banco de origem").click()
    dialog = page.get_by_role("dialog", name="Consultar banco de origem")
    dialog.get_by_role("button", name="Editar produto 101").click()
    dialog.get_by_label("Novo estoque").fill("8")
    dialog.get_by_role("button", name="Salvar estoque").click()
    expect(dialog.get_by_role("row", name="101 Caderno 8")).to_be_visible()
    dialog.get_by_role("button", name="Excluir produto 101").click()
    expect(dialog.locator("#query-status")).to_have_text("1 linha retornada.")
    expect(dialog.get_by_role("row", name="101 Caderno 8")).to_have_count(0)
