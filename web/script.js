"use strict";

const state = {
  files: [], // { id, file, name, result, loading }
  activeId: null,
};

let idCounter = 0;
function nextId() {
  idCounter += 1;
  return "doc-" + idCounter;
}

const els = {
  fileInput: document.getElementById("file"),
  addBtn: document.getElementById("add-btn"),
  docsColumn: document.getElementById("docs-column"),
  docList: document.getElementById("doc-list"),
  uploadZone: document.querySelector(".upload-zone"),
  preview: document.getElementById("pdf-preview"),
  previewEmpty: document.getElementById("preview-empty"),
  result: document.getElementById("result"),
  transBody: document.getElementById("trans-body"),
  copyBtn: document.getElementById("copy-btn"),
  downloadBtn: document.getElementById("download-btn"),
  jsonStatus: document.getElementById("json-status"),
  downloadAllBtn: document.getElementById("download-all-btn"),
  downloadAllLabel: document.getElementById("download-all-label"),
  tabJson: document.getElementById("tab-json"),
  tabTrans: document.getElementById("tab-trans"),
  jsonPane: document.getElementById("json-pane"),
  transPane: document.getElementById("trans-pane"),
};

/* ---- Zakładki wyniku ---- */
function setTab(tab) {
  const isTrans = tab === "trans";
  els.tabJson.classList.toggle("active", !isTrans);
  els.tabTrans.classList.toggle("active", isTrans);
  els.jsonPane.classList.toggle("hidden", isTrans);
  els.transPane.classList.toggle("hidden", !isTrans);
}
els.tabJson.addEventListener("click", () => setTab("json"));
els.tabTrans.addEventListener("click", () => setTab("trans"));

/* ---- Wgrywanie plików ---- */
els.addBtn.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", () => {
  addFiles(els.fileInput.files);
  els.fileInput.value = "";
});

function addFiles(fileList) {
  const incoming = Array.from(fileList || []).filter((f) => /\.pdf$/i.test(f.name));
  if (!incoming.length) {
    return;
  }
  const ids = incoming.map((f) => {
    const item = {
      id: nextId(),
      file: f,
      name: f.name,
      result: null,
      loading: false,
    };
    state.files.push(item);
    return item.id;
  });
  renderList();
  selectFile(ids[0]);
}

/* ---- Drag & drop ---- */
["dragenter", "dragover"].forEach((evt) => {
  els.docsColumn.addEventListener(evt, (e) => {
    e.preventDefault();
    els.uploadZone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((evt) => {
  els.docsColumn.addEventListener(evt, (e) => {
    e.preventDefault();
    els.uploadZone.classList.remove("dragover");
  });
});
els.docsColumn.addEventListener("drop", (e) => {
  e.preventDefault();
  els.uploadZone.classList.remove("dragover");
  if (e.dataTransfer && e.dataTransfer.files) {
    addFiles(e.dataTransfer.files);
  }
});

/* ---- Lista dokumentów ---- */
function renderList() {
  els.docList.innerHTML = "";
  for (const item of state.files) {
    const li = document.createElement("li");
    li.className = "doc-item" + (item.id === state.activeId ? " active" : "");
    li.dataset.id = item.id;

    const sq = document.createElement("span");
    sq.className = "doc-sq " + (item.id === state.activeId ? "active" : "inactive");

    const name = document.createElement("span");
    name.className = "doc-name";
    name.textContent = item.name;
    name.title = item.name;

    const status = document.createElement("span");
    status.className = "doc-status";
    if (item.loading) {
      status.textContent = "przetwarzanie...";
    } else if (item.result && item.result.document_type) {
      status.textContent = item.result.document_type;
      status.classList.add("badge");
    } else if (item.result && item.result.error) {
      status.textContent = "błąd";
      status.classList.add("badge", "badge-error");
    }

    li.append(sq, name, status);
    li.addEventListener("click", () => selectFile(item.id));
    els.docList.appendChild(li);
  }
  updateDownloadAllButton();
}

function selectFile(id) {
  const item = state.files.find((x) => x.id === id);
  if (!item) {
    return;
  }
  state.activeId = id;
  renderList();
  showPreview(item);
  if (item.result) {
    renderResult(item);
  } else {
    runExtract(item);
  }
}

function showPreview(item) {
  const url = URL.createObjectURL(item.file);
  els.preview.src = url;
  els.previewEmpty.style.display = "none";
}

/* ---- Ekstrakcja ---- */
async function runExtract(item) {
  item.loading = true;
  renderList();
  clearResult();

  const formData = new FormData();
  formData.append("file", item.file);

  try {
    const resp = await fetch("/api/extract", { method: "POST", body: formData });
    if (!resp.ok) {
      let detail = resp.statusText;
      try {
        detail = (await resp.json()).detail || detail;
      } catch (_) {
        /* użyj statusText */
      }
      throw new Error(detail);
    }
    item.result = await resp.json();
  } catch (err) {
    item.result = { error: String(err.message || err) };
  } finally {
    item.loading = false;
    renderList();
  }

  if (state.activeId === item.id) {
    renderResult(item);
  }
}

function renderResult(item) {
  const res = item.result || {};
  item.clean = buildCleanResult(res);
  els.result.textContent = JSON.stringify(item.clean, null, 2);
  renderTransparency(res);
}

// Wyciąga same wartości z zagnieżdżonej struktury "data", usuwając obiekty
// transparentności {value, source_text, rule_used} -> zostaje tylko value.
function unwrapCleanJson(node) {
  if (Array.isArray(node)) {
    return node.map(unwrapCleanJson);
  }
  if (node && typeof node === "object") {
    if ("value" in node) {
      return unwrapCleanJson(node.value);
    }
    const out = {};
    for (const [k, v] of Object.entries(node)) {
      out[k] = unwrapCleanJson(v);
    }
    return out;
  }
  return node;
}

// Czysty wynik JSON (bez source_text / rule_used) przeznaczony do zakładki
// "JSON", przycisków "Kopiuj" i "Pobierz .json".
function buildCleanResult(res) {
  if (!res) {
    return {};
  }
  if (res.error) {
    return { error: res.error };
  }
  return {
    filename: res.filename,
    document_type: res.document_type,
    data: unwrapCleanJson(res.data || {}),
  };
}

function clearResult() {
  els.result.textContent = "";
  els.transBody.innerHTML = "";
}

/* ---- Transparentność ---- */
function renderTransparency(res) {
  const rows = [];
  flattenRows(res.data || {}, "", rows);
  els.transBody.innerHTML = "";

  for (const r of rows) {
    const tr = document.createElement("tr");

    const tdPole = document.createElement("td");
    tdPole.textContent = r.pole;

    const tdVal = document.createElement("td");
    tdVal.textContent = r.value;

    const tdSrc = document.createElement("td");
    tdSrc.textContent = r.source;

    const tdRule = document.createElement("td");
    const code = document.createElement("code");
    code.textContent = r.rule;
    tdRule.appendChild(code);

    tr.append(tdPole, tdVal, tdSrc, tdRule);
    els.transBody.appendChild(tr);
  }
}

function flattenRows(node, path, out) {
  if (Array.isArray(node)) {
    node.forEach((item, i) => flattenRows(item, path + "[" + i + "]", out));
    return;
  }
  if (node && typeof node === "object" && "value" in node) {
    const v = node.value;
    if (v && typeof v === "object") {
      flattenRows(v, path, out);
    } else {
      out.push({
        pole: path,
        value: fmt(v),
        source: node.source_text || "",
        rule: node.rule_used || "",
      });
    }
    return;
  }
  if (node && typeof node === "object") {
    for (const [k, child] of Object.entries(node)) {
      flattenRows(child, path ? path + "." + k : k, out);
    }
    return;
  }
  out.push({ pole: path, value: fmt(node), source: "", rule: "" });
}

function fmt(v) {
  if (v === null || v === undefined || v === "") {
    return "\u2014";
  }
  if (typeof v === "boolean") {
    return String(v);
  }
  return String(v);
}

/* ---- Kopiuj / Pobierz ---- */
els.copyBtn.addEventListener("click", async () => {
  const text = els.result.textContent;
  if (!text) {
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  flashStatus("Skopiowano.");
});

els.downloadBtn.addEventListener("click", () => {
  const item = state.files.find((x) => x.id === state.activeId);
  if (!item || !item.clean) {
    return;
  }
  const base = item.name.replace(/\.pdf$/i, "");
  const blob = new Blob([JSON.stringify(item.clean, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = base + ".json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

/* ---- Zbiorcze pobieranie ZIP (czysty JSON, tylko poprawne dokumenty) ---- */
function getReadyItems() {
  return state.files.filter((f) => f.result && !f.result.error);
}

function updateDownloadAllButton() {
  const ready = getReadyItems();
  els.downloadAllBtn.disabled = ready.length === 0;
  els.downloadAllLabel.textContent =
    "Pobierz wszystkie JSON (.zip)" +
    (ready.length ? " [" + ready.length + "]" : "");
}

// Zamienia .pdf -> .json, zachowując podfolder z webkitRelativePath (jeśli jest).
function entryNameFor(item) {
  const rel = item.file && item.file.webkitRelativePath;
  if (rel && rel.indexOf("/") !== -1) {
    return rel.replace(/\.pdf$/i, ".json");
  }
  return item.name.replace(/\.pdf$/i, ".json");
}

// Unika duplikatów nazw: odwolanie.json -> odwolanie_2.json, odwolanie_3.json...
function uniqueEntryName(name, used) {
  if (!used.has(name)) {
    used.add(name);
    return name;
  }
  const dot = name.lastIndexOf(".");
  const stem = dot > 0 ? name.slice(0, dot) : name;
  const ext = dot > 0 ? name.slice(dot) : "";
  let i = 2;
  let candidate;
  do {
    candidate = stem + "_" + i + ext;
    i += 1;
  } while (used.has(candidate));
  used.add(candidate);
  return candidate;
}

els.downloadAllBtn.addEventListener("click", () => {
  const ready = getReadyItems();
  if (!ready.length) {
    return;
  }

  const usedNames = new Set();
  const entries = [];
  for (const item of ready) {
    // Wyłącznie czysty JSON zgodny ze schematem UZP: sama zawartość "data",
    // bez wrappera {filename, document_type, data} i bez obiektów transparentności.
    const cleanData = unwrapCleanJson(item.result.data || {});
    const jsonText = JSON.stringify(cleanData, null, 2);
    const bytes = new TextEncoder().encode(jsonText);
    entries.push({ name: uniqueEntryName(entryNameFor(item), usedNames), data: bytes });
  }

  ZipExport.downloadZip("odwolania2json_wyniki.zip", entries);
});

function flashStatus(msg) {
  els.jsonStatus.textContent = msg;
  setTimeout(() => {
    if (els.jsonStatus.textContent === msg) {
      els.jsonStatus.textContent = "";
    }
  }, 1500);
}

/* ---- Inicjalizacja ---- */
setTab("json");
renderList();
