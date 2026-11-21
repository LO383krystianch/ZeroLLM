"use strict";

const fileInput = document.getElementById("file");
const extractBtn = document.getElementById("extract");
const downloadBtn = document.getElementById("download");
const preview = document.getElementById("pdf-preview");
const result = document.getElementById("result");
const status = document.getElementById("status");

let lastResult = null;

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) {
    return;
  }

  // Podgląd wybranego PDF (blob URL w iframe z wbudowaną przeglądarką PDF).
  const url = URL.createObjectURL(file);
  preview.src = url;

  extractBtn.disabled = false;
  downloadBtn.disabled = true;
  result.textContent = "";
  setStatus("");
});

extractBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  setStatus("Ekstrakcja w toku...");
  extractBtn.disabled = true;

  try {
    const response = await fetch("/api/extract", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = body.detail || detail;
      } catch (_) {
        // ignoruj — użyjemy statusText
      }
      throw new Error(detail);
    }

    lastResult = await response.json();
    result.textContent = JSON.stringify(lastResult, null, 2);
    downloadBtn.disabled = false;
    setStatus("Gotowe.");
  } catch (err) {
    result.textContent = "";
    setStatus("Błąd: " + err.message, true);
  } finally {
    extractBtn.disabled = false;
  }
});

downloadBtn.addEventListener("click", () => {
  if (!lastResult) {
    return;
  }

  const baseName = (fileInput.files[0]?.name || "wynik").replace(/\.pdf$/i, "");
  const fileName = baseName + ".json";

  const blob = new Blob([JSON.stringify(lastResult, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
});

function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}
