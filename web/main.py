import json
import logging
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg
from confluent_kafka import Consumer, KafkaException
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, StringConstraints
from starlette.middleware.trustedhost import TrustedHostMiddleware

TOPIC = "catalogo.public.produtos"
CONNECT = "http://connect:8083/connectors"
STATIC = Path(__file__).with_name("static")
log = logging.getLogger("uvicorn.error")

ProductId = Annotated[int, Field(ge=-2147483648, le=2147483647)]
Stock = Annotated[int, Field(ge=0, le=2147483647)]


class StockUpdate(BaseModel):
    estoque: Stock


class Product(StockUpdate):
    id: ProductId
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def capture_delay(value):
    """Milissegundos entre o commit na origem (source.ts_ms) e o processamento pelo Debezium (ts_ms)."""
    try:
        payload = value["payload"]
        delay = payload["ts_ms"] - payload["source"]["ts_ms"]
    except (TypeError, KeyError):
        return None
    return delay if isinstance(delay, int) and delay >= 0 else None


class EventFeed:
    def __init__(self):
        self.records = deque(maxlen=40)
        self.ready = False
        self.lock = Lock()
        self.stop = Event()

    def run(self):
        consumer = Consumer({
            "bootstrap.servers": "kafka:9092",
            "group.id": "catalogo-interface",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        })
        next_check = 0
        try:
            consumer.subscribe([TOPIC])
            while not self.stop.is_set():
                if time.monotonic() >= next_check:
                    try:
                        consumer.list_topics(timeout=1)
                        ready = True
                    except KafkaException:
                        ready = False
                    with self.lock:
                        self.ready = ready
                    next_check = time.monotonic() + 3

                message = consumer.poll(0.5)
                if message is None or message.error():
                    continue
                try:
                    key = json.loads(message.key())
                    value = json.loads(message.value()) if message.value() is not None else None
                    entry = {
                        "partition": message.partition(),
                        "offset": message.offset(),
                        "id": key["payload"]["id"],
                        "op": value["payload"]["op"] if value is not None else "tombstone",
                        "captura_ms": capture_delay(value),
                        "key": key,
                        "value": value,
                    }
                except (ValueError, TypeError, KeyError):
                    log.warning("Evento inválido no tópico %s, offset %s", TOPIC, message.offset())
                    continue
                with self.lock:
                    self.records.appendleft(entry)
        finally:
            consumer.close()
            with self.lock:
                self.ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    feed = app.state.feed = EventFeed()
    worker = Thread(target=feed.run, daemon=True)
    worker.start()
    try:
        yield
    finally:
        feed.stop.set()
        worker.join()


app = FastAPI(lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def page():
    return FileResponse(STATIC / "index.html")


def query(database, statement, params=()):
    options = "-c statement_timeout=3000"
    if database == "destino":
        options += " -c default_transaction_read_only=on"
    try:
        with psycopg.connect(
            os.environ[f"{database.upper()}_DSN"],
            connect_timeout=2,
            options=options,
            row_factory=dict_row,
        ) as connection:
            return connection.execute(statement, params).fetchall()
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(409, "Já existe um produto com esse ID.") from exc
    except psycopg.Error as exc:
        log.warning("Falha no PostgreSQL de %s (%s)", database, type(exc).__name__)
        raise HTTPException(503, f"Falha ao acessar o PostgreSQL de {database}.") from exc


def require_demo_header(x_cdc_demo: Annotated[str | None, Header()] = None):
    if x_cdc_demo != "1":
        raise HTTPException(403, "Ação permitida pela interface local.")


write_guard = [Depends(require_demo_header)]


PRODUCTS_SQL = "SELECT id, nome, estoque\nFROM public.produtos\nORDER BY id"


@app.get("/api/produtos/{database}")
def products(database: Literal["origem", "destino"]):
    return query(database, PRODUCTS_SQL)


@app.get("/api/consulta/{database}")
def view_database(database: Literal["origem", "destino"]):
    return {"sql": PRODUCTS_SQL + ";", "rows": products(database)}


@app.post("/api/produtos/origem", status_code=201, dependencies=write_guard)
def create(product: Product):
    return query(
        "origem",
        "INSERT INTO public.produtos (id, nome, estoque) VALUES (%s, %s, %s) RETURNING id",
        (product.id, product.nome, product.estoque),
    )[0]


@app.patch("/api/produtos/origem/{product_id}", dependencies=write_guard)
def update(product_id: ProductId, product: StockUpdate):
    rows = query(
        "origem",
        "UPDATE public.produtos SET estoque = %s WHERE id = %s RETURNING id",
        (product.estoque, product_id),
    )
    if not rows:
        raise HTTPException(404, "Produto ausente na origem.")
    return rows[0]


@app.delete("/api/produtos/origem/{product_id}", dependencies=write_guard)
def delete(product_id: ProductId):
    rows = query("origem", "DELETE FROM public.produtos WHERE id = %s RETURNING id", (product_id,))
    if not rows:
        raise HTTPException(404, "Produto ausente na origem.")
    return rows[0]


@app.get("/api/eventos")
def events():
    feed = app.state.feed
    with feed.lock:
        if not feed.ready:
            raise HTTPException(503, "Aguardando conexão com o Kafka.")
        return list(feed.records)


def connect_request(role, path, method="GET"):
    name = f"produtos-{role}"
    try:
        with urlopen(Request(f"{CONNECT}/{name}/{path}", method=method), timeout=3) as response:
            return json.load(response) if method == "GET" else None
    except HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(503, f"Registre o conector {name} no Kafka Connect.") from exc
        raise HTTPException(503, "O Kafka Connect recusou a operação. Tente novamente.") from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(503, "Falha ao acessar o Kafka Connect.") from exc


def connector_status(role):
    status = connect_request(role, "status")
    return {
        "connector": status["connector"]["state"],
        "tasks": [task["state"] for task in status["tasks"]],
    }


@app.get("/api/source")
def source():
    return connector_status("origem")


@app.get("/api/sink")
def sink():
    return connector_status("destino")


@app.put("/api/sink/{action}", status_code=202, dependencies=write_guard)
def set_sink(action: Literal["pause", "resume"]):
    connect_request("destino", action, "PUT")
    return {"accepted": True}
