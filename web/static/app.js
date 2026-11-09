"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("product-form");
const idInput = byId("product-id");
const nameInput = byId("product-name");
const stockInput = byId("product-stock");
const save = byId("save-product");
const cancel = byId("cancel-edit");
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
  form.reset();
  if (product) {
    idInput.value = product.id;
    nameInput.value = product.nome;
    stockInput.value = product.estoque;
    stockInput.focus();
  }
  idInput.readOnly = nameInput.readOnly = Boolean(product);
  cancel.hidden = !product;
  byId("form-title").textContent = product ? "Alterar estoque" : "Novo produto";
  save.textContent = product ? "Salvar estoque" : "Inserir produto";
}

async function productAction(action, onSuccess, success) {
  if (productBusy) return;
  productBusy = true;
  save.disabled = cancel.disabled = true;
  feedback("product-feedback", "Enviando alteração…");
  try {
    await action();
    onSuccess();
    actionResult("product-feedback", success);
  } catch (error) {
    actionResult("product-feedback", error.message, true);
  } finally {
    productBusy = false;
    save.disabled = cancel.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const estoque = stockInput.valueAsNumber;
  if (editing !== null) {
    productAction(() => api("/produtos/origem/" + editing, "PATCH", { estoque }),
      () => setEditing(null), `Estoque do produto ${editing} alterado para ${estoque} na origem.`);
  } else {
    productAction(() => api("/produtos/origem", "POST", {
      id: idInput.valueAsNumber, nome: nameInput.value.trim(), estoque,
    }), () => setEditing(null), `Produto ${idInput.valueAsNumber} inserido na origem.`);
  }
});
cancel.addEventListener("click", () => {
  setEditing(null);
  idInput.focus();
});

function rowButton(text, product, className, action) {
  const button = element("button", text, className);
  button.type = "button";
  button.setAttribute("aria-label", text + " produto " + product.id);
  button.addEventListener("click", () => { if (!productBusy) action(); });
  return button;
}

function productsTable(products, writable) {
  if (!products.length) return element("p", "Nenhum produto neste banco.", "message");
  const table = element("table");
  table.setAttribute("aria-label", writable ? "Produtos na origem" : "Produtos no destino");
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
          productAction(() => api("/produtos/origem/" + product.id, "DELETE"),
            () => { if (editing === product.id) setEditing(null); },
            `Produto ${product.id} excluído da origem.`);
        }),
      );
      row.insertCell().append(actions);
    }
  }
  return table;
}

const operations = { c: "Inserção", u: "Atualização", d: "Exclusão", r: "Snapshot", tombstone: "Tombstone" };

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
    if (rendered.get(id) === key) return;
    byId(id).replaceChildren(render(data));
    rendered.set(id, key);
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

async function refreshSink() {
  const badge = byId("sink-state");
  try {
    const state = await api("/sink");
    const settled = state.tasks.length > 0 && state.tasks.every((task) => task === state.connector);
    const observed = settled ? state.connector : state.tasks.includes("FAILED") ? "FAILED" : "TRANSITION";
    const labels = { RUNNING: "Em execução", PAUSED: "Pausado", FAILED: "Falha", TRANSITION: "Em transição" };
    const label = labels[observed] ?? observed;
    if (badge.textContent !== label) badge.textContent = label;
    badge.dataset.state = observed;
    badge.title = "Conector: " + state.connector + " · Tarefas: " + state.tasks.join(", ");
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
    if (badge.textContent !== "Indisponível") badge.textContent = "Indisponível";
    badge.dataset.state = "FAILED";
    badge.title = error.message;
    pause.disabled = resume.disabled = true;
    if (sinkPending) {
      sinkPending = null;
      actionResult("sink-feedback", error.message, true);
    } else {
      feedback("sink-feedback", error.message, true);
    }
  }
}

async function refresh() {
  await Promise.all([
    panel("origem-data", "/produtos/origem", (data) => productsTable(data, true)),
    panel("destino-data", "/produtos/destino", (data) => productsTable(data, false)),
    panel("events-data", "/eventos", eventsList),
    refreshSink(),
  ]);
  setTimeout(refresh, 1000);
}

refresh();
