"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("product-form");
const idInput = byId("product-id");
const nameInput = byId("product-name");
const stockInput = byId("product-stock");
const save = byId("save-product");
const editForm = byId("query-edit-form");
const editStock = byId("query-edit-stock");
const editSave = byId("query-save");
const pause = byId("pause");
const resume = byId("resume");
let editing = null;
let productBusy = false;
let sinkPending = null;
let notificationTimer;
const rendered = new Map();

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function api(path, method = "GET", data) {
  const response = await fetch("/api" + path, {
    method,
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
    headers: method === "GET" ? {} : {
      "Content-Type": "application/json",
      "X-CDC-Demo": "1",
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  }).catch(() => { throw new Error("Falha de conexão com a interface. Tente novamente."); });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(typeof result.detail === "string" ? result.detail : "Confira os campos e tente novamente.");
  }
  return result;
}

function feedback(id, text, failed = false) {
  const node = byId(id);
  if (node.textContent !== text) node.textContent = text;
  node.classList.toggle("error", failed);
}

function actionResult(id, text, failed = false) {
  feedback(id, text, failed);
  const notification = byId("notification");
  notification.classList.toggle("error", failed);
  notification.replaceChildren(text);
  clearTimeout(notificationTimer);
  notificationTimer = setTimeout(() => notification.replaceChildren(), 4500);
}

function setEditing(product) {
  editing = product?.id ?? null;
  editForm.hidden = !product;
  if (product) {
    byId("query-edit-title").textContent = `Alterar estoque do produto ${product.id}`;
    editStock.value = product.estoque;
    editStock.focus();
  }
}

async function productAction(action, onSuccess, success, feedbackId = "product-feedback") {
  if (productBusy) return;
  productBusy = true;
  save.disabled = editSave.disabled = true;
  feedback(feedbackId, "Enviando alteração…");
  try {
    await action();
    onSuccess();
    actionResult(feedbackId, success);
  } catch (error) {
    actionResult(feedbackId, error.message, true);
  } finally {
    productBusy = false;
    save.disabled = editSave.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const id = idInput.valueAsNumber;
  productAction(() => api("/produtos/origem", "POST", {
    id, nome: nameInput.value.trim(), estoque: stockInput.valueAsNumber,
  }), () => form.reset(), `Produto ${id} inserido na origem.`);
});

function rowButton(text, product, className, action) {
  const button = element("button", text, className);
  button.type = "button";
  button.setAttribute("aria-label", text + " produto " + product.id);
  button.addEventListener("click", () => { if (!productBusy) action(); });
  return button;
}

function productsTable(products, writable, label) {
  if (!products.length) return element("p", "Nenhum produto neste banco.", "message");
  const table = element("table");
  table.setAttribute("aria-label", label ?? (writable ? "Produtos na origem" : "Produtos no destino"));
  const head = table.createTHead().insertRow();
  const headings = writable ? ["ID", "Nome", "Estoque", "Ações"] : ["ID", "Nome", "Estoque"];
  for (const title of headings) {
    const cell = element("th", title);
    cell.scope = "col";
    head.append(cell);
  }
  const body = table.createTBody();
  for (const product of products) {
    const row = body.insertRow();
    row.insertCell().append(element("span", product.id, "number"));
    row.insertCell().textContent = product.nome;
    row.insertCell().append(element("span", product.estoque, "number"));
    if (writable) {
      const actions = element("div", undefined, "row-actions");
      actions.append(
        rowButton("Editar", product, "secondary", () => setEditing(product)),
        rowButton("Excluir", product, "danger", () => {
          if (!window.confirm("Excluir o produto " + product.id + " da origem?")) return;
          changeProductInDialog(product.id, "DELETE", undefined,
            `Produto ${product.id} excluído da origem.`);
        }),
      );
      row.insertCell().append(actions);
    }
  }
  return table;
}

const queryDialog = byId("database-query");
const queryOutput = byId("query-output");
const queryRefresh = byId("query-refresh");
let queryBank;
let queryRequest;

for (const button of document.querySelectorAll("[data-query-bank]")) {
  button.addEventListener("click", () => {
    queryBank = button.dataset.queryBank;
    setEditing(null);
    byId("query-action-feedback").hidden = queryBank !== "origem";
    feedback("query-action-feedback", "");
    byId("query-title").textContent = button.getAttribute("aria-label");
    byId("query-sql-details").open = false;
    queryDialog.showModal();
    loadDatabase();
  });
}

byId("query-close").addEventListener("click", () => queryDialog.close());

async function loadDatabase() {
  const request = queryRequest = Symbol();
  const bank = queryBank;
  queryOutput.hidden = true;
  queryRefresh.disabled = true;
  feedback("query-status", "Consultando o PostgreSQL…");
  try {
    const result = await api(`/consulta/${bank}`);
    if (queryRequest !== request || !queryDialog.open) return;
    byId("query-sql").textContent = result.sql;
    const rows = productsTable(result.rows, bank === "origem");
    if (result.rows.length) rows.setAttribute("aria-label", `Produtos no banco de ${bank}`);
    byId("query-rows").replaceChildren(rows);
    const count = result.rows.length;
    feedback("query-status", count === 1 ? "1 linha retornada." : `${count} linhas retornadas.`);
    queryOutput.hidden = false;
  } catch (error) {
    if (queryRequest === request && queryDialog.open) feedback("query-status", error.message, true);
  } finally {
    if (queryRequest === request) queryRefresh.disabled = false;
  }
}

queryRefresh.addEventListener("click", loadDatabase);

function changeProductInDialog(id, method, data, message) {
  productAction(() => api(`/produtos/origem/${id}`, method, data), () => {
    if (queryDialog.open && queryBank === "origem") {
      if (editing === id) setEditing(null);
      loadDatabase();
    }
  }, message, "query-action-feedback");
}

editForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (editing === null) return;
  const estoque = editStock.valueAsNumber;
  changeProductInDialog(editing, "PATCH", { estoque },
    `Estoque do produto ${editing} alterado para ${estoque} na origem.`);
});

byId("query-cancel-edit").addEventListener("click", () => {
  setEditing(null);
  queryRefresh.focus();
});

const operations = { c: "Inserção", u: "Atualização", d: "Exclusão", r: "Snapshot", tombstone: "Tombstone" };
const elapsedSeconds = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
let latestChange = null;
let measurement = null;

// Tempo desde o commit na origem (source.ts_ms). Os contêineres e o navegador usam o relógio da mesma máquina.
function formatElapsed(commitMs) {
  return elapsedSeconds.format(Math.max(0, Date.now() - commitMs) / 1000) + " s";
}

function commitTime(event) {
  const payload = event.value.payload;
  return Number.isFinite(payload.source?.ts_ms) ? payload.source.ts_ms : payload.ts_ms;
}

function observeChange(events) {
  if (!events) return;
  const event = events.find((entry) => ["c", "u", "d"].includes(entry.op) &&
    entry.value.payload.ts_ms >= performance.timeOrigin);
  const identity = event ? `${event.partition}:${event.offset}:${event.value.payload.ts_ms}` : null;
  const previous = latestChange;
  latestChange = identity;
  if (!event || previous === identity) return;

  clearInterval(measurement?.ticker);
  const started = commitTime(event);
  const elapsed = byId("replication-elapsed");
  elapsed.hidden = false;
  const tick = () => { elapsed.textContent = formatElapsed(started); };
  tick();
  measurement = { event, started, ticker: setInterval(tick, 100) };
  byId("replication-status").textContent =
    `Aguardando no destino: ${operations[event.op].toLowerCase()} do produto ${event.id}.`;
}

function confirmDestination(products) {
  if (!measurement || !products) return;
  const { event, started, ticker } = measurement;
  const row = products.find((product) => product.id === event.id);
  const after = event.value.payload.after;
  const confirmed = event.op === "d" ? !row : row && after &&
    row.nome === after.nome && row.estoque === after.estoque;
  if (!confirmed) return;

  clearInterval(ticker);
  measurement = null;
  const elapsed = formatElapsed(started);
  byId("replication-elapsed").textContent = elapsed;
  byId("replication-status").textContent =
    `${operations[event.op]} do produto ${event.id} confirmada no destino ${elapsed} após o commit na origem.`;
}

function eventsList(events) {
  if (!events.length) return element("p", "Aguardando o primeiro evento do catálogo.", "message");
  const container = document.createDocumentFragment();
  const open = new Set(Array.from(byId("events-data").querySelectorAll("details[open]"), (node) => node.dataset.event));
  for (const event of events) {
    const details = element("details");
    details.dataset.event = event.partition + ":" + event.offset;
    details.open = open.has(details.dataset.event);
    const summary = element("summary");
    summary.append(element("span", "ID " + event.id, "number"),
      element("span", operations[event.op] ?? event.op, "badge"));
    if (Number.isInteger(event.captura_ms)) {
      const delay = element("span", `captura ${event.captura_ms} ms`, "latency");
      delay.title = "Diferença entre source.ts_ms (commit na origem) e ts_ms (processamento pelo Debezium)";
      summary.append(delay);
    }
    summary.append(element("span", "Ver JSON"));
    const json = JSON.stringify({ chave: event.key, valor: event.value }, null, 2);
    const payload = element("pre", json);
    payload.tabIndex = 0;
    payload.setAttribute("aria-label", "JSON do evento");
    details.append(summary, payload);
    container.append(details);
  }
  return container;
}

async function panel(id, path, render) {
  try {
    const data = await api(path);
    const key = JSON.stringify(data);
    if (rendered.get(id) !== key) {
      byId(id).replaceChildren(render(data));
      rendered.set(id, key);
    }
    return data;
  } catch (error) {
    if (rendered.get(id) === error.message) return;
    byId(id).replaceChildren(element("p", error.message, "message error"));
    rendered.set(id, error.message);
  }
}

async function changeSink(action, target) {
  sinkPending = { target, until: performance.now() + 12000 };
  pause.disabled = resume.disabled = true;
  feedback("sink-feedback", "Aguardando confirmação do Kafka Connect…");
  try {
    await api("/sink/" + action, "PUT");
  } catch (error) {
    sinkPending = null;
    actionResult("sink-feedback", error.message, true);
  }
}

pause.addEventListener("click", () => changeSink("pause", "PAUSED"));
resume.addEventListener("click", () => changeSink("resume", "RUNNING"));

function showConnectorState(id, state) {
  const badge = byId(id);
  const settled = state.tasks.length > 0 && state.tasks.every((task) => task === state.connector);
  const failed = state.connector === "FAILED" || state.tasks.includes("FAILED");
  const observed = failed ? "FAILED" : settled ? state.connector : "TRANSITION";
  const labels = { RUNNING: "Em execução", PAUSED: "Pausado", FAILED: "Falha", TRANSITION: "Em transição" };
  const label = labels[observed] ?? observed;
  if (badge.textContent !== label) badge.textContent = label;
  badge.dataset.state = observed;
  badge.title = "Conector: " + state.connector + " · Tarefas: " + state.tasks.join(", ");
  return observed;
}

function showConnectorUnavailable(id, error) {
  const badge = byId(id);
  if (badge.textContent !== "Indisponível") badge.textContent = "Indisponível";
  badge.dataset.state = "FAILED";
  badge.title = error.message;
}

async function refreshSource() {
  try {
    const observed = showConnectorState("source-state", await api("/source"));
    const activity = {
      RUNNING: "Acompanha o WAL da origem e publica as mudanças no Kafka.",
      PAUSED: "Captura pausada. O conector aguarda a retomada.",
      FAILED: "Falha no conector de captura. Confira o Kafka Connect.",
    };
    feedback("source-activity", activity[observed] ?? "Aguardando a tarefa de captura.", observed === "FAILED");
  } catch (error) {
    showConnectorUnavailable("source-state", error);
    feedback("source-activity", error.message, true);
  }
}

async function refreshSink() {
  try {
    const observed = showConnectorState("sink-state", await api("/sink"));
    const activity = {
      RUNNING: "Consome eventos do Kafka e grava as alterações no PostgreSQL de destino.",
      PAUSED: "Aplicação pausada. Os eventos continuam no tópico Kafka.",
      FAILED: "Falha no conector de destino. Confira o Kafka Connect.",
    };
    feedback("sink-activity", activity[observed] ?? "Aguardando a tarefa de destino.", observed === "FAILED");
    if (sinkPending?.target === observed) {
      actionResult("sink-feedback", observed === "PAUSED" ? "Sink pausado." : "Sink retomado.");
      sinkPending = null;
    } else if (sinkPending && (performance.now() > sinkPending.until || observed === "FAILED")) {
      actionResult("sink-feedback", "A mudança de estado não foi confirmada.", true);
      sinkPending = null;
    }
    pause.disabled = Boolean(sinkPending) || observed !== "RUNNING";
    resume.disabled = Boolean(sinkPending) || observed !== "PAUSED";
  } catch (error) {
    showConnectorUnavailable("sink-state", error);
    feedback("sink-activity", "A aplicação no destino está com estado indisponível.", true);
    pause.disabled = resume.disabled = true;
    if (sinkPending) {
      sinkPending = null;
      actionResult("sink-feedback", error.message, true);
    } else {
      feedback("sink-feedback", error.message, true);
    }
  }
}

async function refreshReplication() {
  const [events, destination] = await Promise.all([
    panel("events-data", "/eventos", eventsList),
    panel("destino-data", "/produtos/destino", (data) => productsTable(data, false, "Produtos no destino")),
    panel("origem-data", "/produtos/origem", (data) => productsTable(data, false, "Produtos na origem")),
  ]);
  if (events) {
    const last = events.find((event) => event.op !== "tombstone");
    feedback("source-last-event", last
      ? `Último evento observado: ${operations[last.op] ?? last.op} do produto ${last.id}.`
      : "Nenhum evento observado.");
  }
  observeChange(events);
  confirmDestination(destination);
}

// Eventos e bancos a cada 0,3 s, para que o cronômetro tenha boa resolução.
async function replicationLoop() {
  await refreshReplication();
  setTimeout(replicationLoop, 300);
}

// Estado dos conectores no Kafka Connect a cada 1 s.
async function connectorLoop() {
  await Promise.all([refreshSource(), refreshSink()]);
  setTimeout(connectorLoop, 1000);
}

replicationLoop();
connectorLoop();
