"""Refaz o ensaio da demonstração e gera as capturas e o registro de verificação.

Uso, na raiz do projeto, com o ambiente recém-criado pelo inicializador:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\\iniciar-web.ps1   (ou ./iniciar-web.sh)
    python scripts/gerar-evidencias.py

Requer Python com Playwright (pip install playwright e python -m playwright install chromium).
As capturas vão para evidencias/etapa-5 e substituem as anteriores.
"""
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evidencias" / "etapa-5"
URL = "http://127.0.0.1:18000/"
COMPOSE = ["docker", "compose", "-p", "debezium-pgbd-demo-vazia",
           "-f", str(ROOT / "compose.yaml"), "-f", str(ROOT / "compose.demo.yaml")]
TIMEOUT = 20_000


def docker_sql(database, statement):
    result = subprocess.run(
        [*COMPOSE, "exec", "-T", database, "psql", "-X", "-U", "postgres", "-d", "catalogo", "-c", statement],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return result.stdout.rstrip()


class Rehearsal:
    def __init__(self, page, sql, log):
        self.page = page
        self.sql = sql
        self.log = log
        self.started = time.monotonic()

    def mark(self, text):
        self.log(f"\n[{time.monotonic() - self.started:.1f} s] {text}")

    def query(self, database, statement):
        self.log(f"\n[{database}] {statement}")
        self.log(self.sql(database, statement))

    def compare(self, product_id):
        statement = f"SELECT id, nome, estoque FROM public.produtos WHERE id = {product_id};"
        self.query("origem", statement)
        self.query("destino", statement)

    def kafka(self, product_id, operations):
        events = self.page.evaluate("fetch('/api/eventos').then((r) => r.json())")
        mine = [e for e in reversed(events) if e["id"] == product_id and e["op"] in operations]
        for event in mine:
            delay = f", captura={event['captura_ms']} ms" if event.get("captura_ms") is not None else ""
            self.log(f"Kafka: chave id={product_id}, evento={event['op']}, "
                     f"partição:offset={event['partition']}:{event['offset']}{delay}")

    def timer(self):
        status = self.page.locator("#replication-status").inner_text()
        self.log(f"Interface: {status}")

    def shot(self, name, locator=None):
        # A notificação flutuante cobriria parte dos painéis na captura.
        self.page.evaluate("document.getElementById('notification').replaceChildren()")
        (locator or self.page.locator(".flow")).screenshot(path=OUT / name)
        self.log(f"Captura: {name}")

    def insert(self, product_id, name, stock):
        page = self.page
        page.fill("#product-id", str(product_id))
        page.fill("#product-name", name)
        page.fill("#product-stock", str(stock))
        page.click("#save-product")
        expect(page.locator("#product-feedback")).to_have_text(f"Produto {product_id} inserido na origem.")

    def confirmed(self, text):
        expect(self.page.locator("#replication-status")).to_contain_text(text, timeout=TIMEOUT)

    def open_query(self, bank, rows):
        page = self.page
        page.get_by_role("button", name=f"Consultar banco de {bank}").click()
        dialog = page.get_by_role("dialog", name=f"Consultar banco de {bank}")
        expect(dialog.locator("#query-status")).to_have_text(rows)
        return dialog

    def run(self):
        page = self.page
        page.goto(URL)
        expect(page.locator("#source-state")).to_have_text("Em execução", timeout=TIMEOUT)
        expect(page.locator("#sink-state")).to_have_text("Em execução", timeout=TIMEOUT)
        expect(page.locator("#origem-data")).to_contain_text("Nenhum produto")
        expect(page.locator("#destino-data")).to_contain_text("Nenhum produto")
        self.log("Estado inicial: dois bancos vazios e os dois conectores em execução.")

        self.mark("Passo 1: inserção de 101 (Caderno, estoque 10) pela tela")
        self.insert(101, "Caderno", 10)
        self.confirmed("Inserção do produto 101 confirmada no destino")
        self.kafka(101, {"c"})
        self.timer()
        self.compare(101)
        self.shot("01-insercao.png")

        self.mark("Passo 2: UPDATE pelo psql da origem")
        self.query("origem", "UPDATE public.produtos SET estoque = 7 WHERE id = 101;")
        self.confirmed("Atualização do produto 101 confirmada no destino")
        self.kafka(101, {"u"})
        self.timer()
        self.compare(101)
        self.shot("02-atualizacao.png")

        self.mark("Passo 3: exclusão de 101 pela janela Consultar banco")
        dialog = self.open_query("origem", "1 linha retornada.")
        page.once("dialog", lambda confirmation: confirmation.accept())
        dialog.get_by_role("button", name="Excluir produto 101").click()
        expect(dialog.locator("#query-status")).to_have_text("0 linhas retornadas.")
        dialog.locator("#query-close").click()
        self.confirmed("Exclusão do produto 101 confirmada no destino")
        expect(page.locator("#events-data")).to_contain_text("Tombstone")
        self.kafka(101, {"d", "tombstone"})
        self.timer()
        self.compare(101)
        self.shot("03-exclusao.png")

        self.mark("Passo 4: pausa do sink e inserção de 102 (Caneta, estoque 10)")
        page.click("#pause")
        expect(page.locator("#sink-state")).to_have_text("Pausado", timeout=TIMEOUT)
        self.insert(102, "Caneta", 10)
        expect(page.locator("#replication-status")).to_have_text(
            "Aguardando no destino: inserção do produto 102.", timeout=TIMEOUT)
        page.wait_for_timeout(1500)
        self.kafka(102, {"c"})
        self.timer()
        self.compare(102)
        self.shot("04-sink-pausado.png")
        dialog = self.open_query("origem", "1 linha retornada.")
        self.shot("06-consulta-origem.png", dialog)
        dialog.locator("#query-close").click()
        dialog = self.open_query("destino", "0 linhas retornadas.")
        self.shot("07-consulta-destino.png", dialog)
        dialog.locator("#query-close").click()

        self.mark("Passo 5: retomada do sink")
        page.click("#resume")
        expect(page.locator("#sink-state")).to_have_text("Em execução", timeout=TIMEOUT)
        self.confirmed("Inserção do produto 102 confirmada no destino")
        self.timer()
        self.compare(102)
        self.shot("05-sink-retomado.png")

        self.mark("Roteiro concluído")


def main():
    lines = []

    def log(text):
        print(text, flush=True)
        lines.append(text)

    log(f"Ensaio gerado por scripts/gerar-evidencias.py em {time.strftime('%Y-%m-%d %H:%M:%S %z')}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
        try:
            Rehearsal(page, docker_sql, log).run()
        except Exception:
            # Preserva o registro anterior: a falha vai para arquivos separados.
            page.screenshot(path=OUT / "falha-ensaio.png", full_page=True)
            log("Falha no ensaio. Veja evidencias/etapa-5/falha-ensaio.png.")
            (OUT / "verificacao-falha.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            raise
        finally:
            browser.close()
    (OUT / "verificacao.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
