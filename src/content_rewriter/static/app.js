const el = (id) => document.getElementById(id);

const editor = el("editor");
const sourceRendered = el("sourceRendered");
const resultRendered = el("resultRendered");
const chip = el("chip");
const chipName = el("chipName");
const runButton = el("run");
const copyButton = el("copy");
const downloadButton = el("download");
const fileInput = el("fileInput");
const banner = el("banner");
const chunk = el("chunk");
const dot = el("dot");

const state = {
  file: null,
  sourceLength: 0,
  resultText: "",
  filename: "rewritten.txt",
  busy: false,
};

function setStatus(text, tone) {
  el("statusText").textContent = text;
  dot.className = "dot" + (tone ? " " + tone : "");
}

function showBanner(text, tone, action) {
  banner.className = "banner" + (tone ? " " + tone : "");
  el("bannerText").textContent = text;
  const button = el("bannerAction");
  if (action) {
    button.textContent = action.label;
    button.onclick = action.run;
    button.hidden = false;
  } else {
    button.hidden = true;
  }
  banner.hidden = false;
}

function hideBanner() {
  banner.hidden = true;
}

function setProgress(value) {
  chunk.style.width = value + "%";
}

function syncCount() {
  state.sourceLength = state.file ? state.sourceLength : editor.value.length;
  el("sourceCount").textContent = state.sourceLength.toLocaleString() + " characters";
}

function showSource(kind, text, html) {
  state.sourceLength = text.length;
  if (kind === "markdown") {
    sourceRendered.innerHTML = html;
    sourceRendered.hidden = false;
    editor.hidden = true;
  } else {
    editor.value = text;
    editor.readOnly = true;
    editor.hidden = false;
    sourceRendered.hidden = true;
  }
  syncCount();
}

async function loadFile(file) {
  const body = new FormData();
  body.append("file", file);

  try {
    const response = await fetch("/api/preview", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Could not read that file.");

    state.file = file;
    chipName.textContent = payload.name + "  ·  " + readableSize(file.size);
    chip.hidden = false;
    showSource(payload.kind, payload.text, payload.html);
    hideBanner();
    setStatus("File loaded", null);
  } catch (error) {
    showBanner(error.message, "error");
    setStatus("Error", "error");
  }
}

function clearFile() {
  state.file = null;
  chip.hidden = true;
  editor.readOnly = false;
  editor.value = "";
  editor.hidden = false;
  sourceRendered.hidden = true;
  setStatus("Ready", null);
  syncCount();
}

function readableSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

async function run() {
  if (state.busy) return;
  if (!state.file && !editor.value.trim()) {
    showBanner("Add some text or open a file first.", "error");
    return;
  }

  const body = new FormData();
  if (state.file) body.append("file", state.file);
  else body.append("text", editor.value);

  state.busy = true;
  runButton.disabled = true;
  runButton.textContent = "Working";
  copyButton.disabled = true;
  downloadButton.disabled = true;
  resultRendered.innerHTML = "";
  el("resultCount").textContent = "";
  hideBanner();
  setStatus("Working", "working");
  setProgress(6);

  try {
    const response = await fetch("/api/rewrite", { method: "POST", body });
    if (!response.ok) {
      fail({ error: await describeFailure(response) });
      return;
    }

    for await (const event of readEvents(response)) {
      if (event.stage) {
        el("stage").textContent = event.label;
        setProgress(event.progress);
      } else if (event.done) {
        finish(event);
      } else if (event.error) {
        fail(event);
      }
    }
  } catch (error) {
    fail({ error: error.message });
  } finally {
    state.busy = false;
    runButton.disabled = false;
    runButton.textContent = "Humanise";
  }
}

async function describeFailure(response) {
  const fallback = "The server rejected that request (" + response.status + ").";
  try {
    const payload = await response.json();
    return payload.detail || fallback;
  } catch (unreadableBody) {
    return fallback;
  }
}

async function* readEvents(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (line.trim()) yield JSON.parse(line);
    }
  }
  if (buffer.trim()) yield JSON.parse(buffer);
}

function finish(payload) {
  state.resultText = payload.text;
  state.filename = payload.filename;
  resultRendered.innerHTML = payload.html;
  resultRendered.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 420, easing: "ease-out" });
  el("resultCount").textContent = payload.text.length.toLocaleString() + " characters";
  el("stage").textContent = "Finished";
  copyButton.disabled = false;
  downloadButton.disabled = false;
  setProgress(100);
  setStatus("Done", null);
  setTimeout(() => setProgress(0), 2400);
}

function fail(payload) {
  el("stage").textContent = "Failed";
  setProgress(0);
  setStatus("Error", "error");
  showBanner(payload.error + (payload.log ? "  (wrote " + payload.log + ")" : ""), "error");
}

async function download() {
  const response = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: state.resultText, filename: state.filename }),
  });

  if (!response.ok) {
    showBanner("Could not build that file.", "error");
    return;
  }

  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = state.filename;
  link.click();
  URL.revokeObjectURL(url);
}

runButton.addEventListener("click", run);
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(state.resultText);
  showBanner("Copied to clipboard.", "success");
  setTimeout(hideBanner, 1800);
});
downloadButton.addEventListener("click", download);
el("openFile").addEventListener("click", () => fileInput.click());
el("chipClear").addEventListener("click", clearFile);
el("bannerDismiss").addEventListener("click", hideBanner);
editor.addEventListener("input", syncCount);

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) loadFile(fileInput.files[0]);
  fileInput.value = "";
});

const card = el("sourceCard");
["dragenter", "dragover"].forEach((name) =>
  card.addEventListener(name, (event) => {
    event.preventDefault();
    card.classList.add("dragging");
  })
);
["dragleave", "drop"].forEach((name) =>
  card.addEventListener(name, (event) => {
    event.preventDefault();
    card.classList.remove("dragging");
  })
);
card.addEventListener("drop", (event) => {
  if (event.dataTransfer.files.length) loadFile(event.dataTransfer.files[0]);
});

document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") run();
});

syncCount();
