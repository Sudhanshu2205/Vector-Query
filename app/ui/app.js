const uploadForm = document.getElementById("upload-form");
const queryForm = document.getElementById("query-form");
const fileInput = document.getElementById("file-input");
const dropzone = document.getElementById("dropzone");
const selectedFile = document.getElementById("selected-file");
const uploadButton = document.getElementById("upload-button");
const queryButton = document.getElementById("query-button");
const currentDocId = document.getElementById("current-doc-id");
const processingStatus = document.getElementById("processing-status");
const statusPill = document.getElementById("status-pill");
const questionInput = document.getElementById("question-input");
const topKInput = document.getElementById("top-k-input");
const answerContent = document.getElementById("answer-content");
const answerBanner = document.getElementById("answer-banner");
const sourceList = document.getElementById("source-list");
const historyList = document.getElementById("history-list");
const metricsGrid = document.getElementById("metrics-grid");

const HISTORY_KEY = "vectorquery-ui-history";
let activeDocId = null;
let statusPollTimer = null;
let historyItems = loadHistory();

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory() {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(historyItems.slice(0, 8)));
}

function setSelectedFileLabel(file) {
  selectedFile.textContent = file ? `${file.name} (${formatBytes(file.size)})` : "None";
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function setStatus(status, text) {
  statusPill.textContent = status;
  statusPill.className = "status-pill";

  if (status === "Processing") statusPill.classList.add("processing");
  if (status === "Completed") statusPill.classList.add("completed");
  if (status === "Failed") statusPill.classList.add("failed");

  processingStatus.textContent = text;
}

function clearPoller() {
  if (statusPollTimer) {
    clearTimeout(statusPollTimer);
    statusPollTimer = null;
  }
}

function rememberDocument(docId, label, status) {
  const nextItem = {
    docId,
    label,
    status,
    savedAt: new Date().toISOString(),
  };

  historyItems = [
    nextItem,
    ...historyItems.filter((item) => item.docId !== docId),
  ].slice(0, 8);

  saveHistory();
  renderHistory();
}

function updateHistoryStatus(docId, status) {
  historyItems = historyItems.map((item) =>
    item.docId === docId ? { ...item, status } : item
  );
  saveHistory();
  renderHistory();
}

function renderHistory() {
  if (!historyItems.length) {
    historyList.innerHTML = '<p class="empty-state">Uploaded documents will appear here for quick reuse.</p>';
    return;
  }

  historyList.innerHTML = historyItems
    .map((item) => `
      <article class="history-card">
        <div class="history-meta">
          <p class="meta-label">${item.status || "unknown"}</p>
          <p>${item.label || "Uploaded document"}</p>
          <p class="doc-id">${item.docId}</p>
        </div>
        <button
          class="history-button ${item.docId === activeDocId ? "active" : ""}"
          data-doc-id="${item.docId}"
          type="button"
        >
          Use
        </button>
      </article>
    `)
    .join("");

  historyList.querySelectorAll(".history-button").forEach((button) => {
    button.addEventListener("click", () => {
      const docId = button.dataset.docId;
      activeDocId = docId;
      currentDocId.textContent = docId;
      setStatus("Ready", "Selected from recent documents");
      renderHistory();
    });
  });
}

function renderMetrics(metrics) {
  const items = [
    ["Total latency", formatMetric(metrics.total_latency_ms)],
    ["Embedding", formatMetric(metrics.embedding_time_ms)],
    ["Retrieval", formatMetric(metrics.retrieval_time_ms)],
    ["Generation", formatMetric(metrics.llm_generation_time_ms)],
  ];

  metricsGrid.innerHTML = items
    .map(([label, value]) => `
      <article class="metric-card">
        <p class="meta-label">${label}</p>
        <p class="metric-value">${value}</p>
      </article>
    `)
    .join("");
}

function formatMetric(value) {
  if (value === undefined || value === null) return "--";
  return `${Number(value).toFixed(2)} ms`;
}

function renderSources(sources) {
  if (!sources || !sources.length) {
    sourceList.innerHTML = '<p class="empty-state">No sources were returned for this query.</p>';
    return;
  }

  sourceList.innerHTML = sources
    .map((source) => `
      <article class="source-card">
        <div class="source-head">
          <p class="meta-label">Chunk ${source.chunk_id}</p>
          <p class="source-score">Score ${Number(source.score).toFixed(4)}</p>
        </div>
        <p class="source-text">${escapeHtml(source.text)}</p>
      </article>
    `)
    .join("");
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

async function pollStatus(docId) {
  clearPoller();

  try {
    const response = await fetch(`/upload/status/${docId}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Could not fetch processing status.");
    }

    if (payload.status === "completed") {
      setStatus("Completed", "Document is ready for questions.");
      updateHistoryStatus(docId, "completed");
      return;
    }

    if (payload.status.startsWith("failed")) {
      setStatus("Failed", payload.status);
      updateHistoryStatus(docId, "failed");
      return;
    }

    setStatus("Processing", payload.status);
    statusPollTimer = setTimeout(() => pollStatus(docId), 1500);
  } catch (error) {
    setStatus("Failed", error.message);
  }
}

async function handleUpload(event) {
  event.preventDefault();
  const file = fileInput.files[0];

  if (!file) {
    setStatus("Failed", "Select a PDF or TXT file before uploading.");
    return;
  }

  uploadButton.disabled = true;
  uploadButton.textContent = "Uploading...";
  setStatus("Processing", "Sending file to the API...");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/upload", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Upload failed.");
    }

    activeDocId = payload.doc_id;
    currentDocId.textContent = activeDocId;
    rememberDocument(activeDocId, file.name, payload.status);
    setStatus("Processing", "Document uploaded. Building embeddings now...");
    pollStatus(activeDocId);
  } catch (error) {
    setStatus("Failed", error.message);
  } finally {
    uploadButton.disabled = false;
    uploadButton.textContent = "Start Processing";
  }
}

async function handleQuery(event) {
  event.preventDefault();

  if (!activeDocId) {
    setStatus("Failed", "Upload or select a document before running a query.");
    return;
  }

  const question = questionInput.value.trim();
  if (!question) {
    setStatus("Failed", "Enter a question first.");
    return;
  }

  queryButton.disabled = true;
  queryButton.textContent = "Querying...";
  answerContent.textContent = "Running retrieval and answer generation...";
  answerBanner.classList.add("hidden");

  try {
    const response = await fetch("/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        doc_id: activeDocId,
        top_k: Number(topKInput.value) || 3,
      }),
    });

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Query failed.");
    }

    answerContent.textContent = payload.answer;
    renderMetrics(payload.metrics || {});
    renderSources(payload.sources || []);

    if (payload.answer.startsWith("[Local fallback answer]")) {
      answerBanner.textContent =
        "OpenAI was unavailable, so the app returned a grounded local fallback answer.";
      answerBanner.classList.remove("hidden");
    } else {
      answerBanner.classList.add("hidden");
    }

    setStatus("Completed", "Latest query completed successfully.");
  } catch (error) {
    answerContent.textContent = error.message;
    answerBanner.textContent = "The query failed before a full answer could be generated.";
    answerBanner.classList.remove("hidden");
    renderSources([]);
    renderMetrics({});
    setStatus("Failed", error.message);
  } finally {
    queryButton.disabled = false;
    queryButton.textContent = "Run Query";
  }
}

fileInput.addEventListener("change", () => {
  setSelectedFileLabel(fileInput.files[0]);
});

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("dragging");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragging");
});

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("dragging");

  const [file] = event.dataTransfer.files;
  if (!file) return;

  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  fileInput.files = dataTransfer.files;
  setSelectedFileLabel(file);
});

document.querySelectorAll(".prompt-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    questionInput.value = chip.dataset.question || "";
    questionInput.focus();
  });
});

uploadForm.addEventListener("submit", handleUpload);
queryForm.addEventListener("submit", handleQuery);

renderHistory();
renderMetrics({});
