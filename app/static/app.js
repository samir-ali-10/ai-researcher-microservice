const queryEl = document.getElementById("query");
const submitBtn = document.getElementById("submit-btn");
const statusLine = document.getElementById("status-line");
const reportEl = document.getElementById("report");
const errorBox = document.getElementById("error-box");

const confidenceEl = document.getElementById("confidence");
const cacheFlagEl = document.getElementById("cache-flag");
const webFlagEl = document.getElementById("web-flag");
const kbFlagEl = document.getElementById("kb-flag");
const reportQueryEl = document.getElementById("report-query");
const summaryEl = document.getElementById("summary");
const findingsEl = document.getElementById("findings");
const internalEl = document.getElementById("internal");
const externalEl = document.getElementById("external");
const taskMetaEl = document.getElementById("task-meta");

const POLL_MS = 1200;

function setBusy(busy, message = "") {
  submitBtn.disabled = busy;
  statusLine.textContent = message;
  statusLine.classList.toggle("busy", Boolean(busy && message));
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderReport(taskId, payload) {
  const report = payload?.report ?? payload;
  const cached = Boolean(payload?.cached);
  const usedWeb = Boolean(payload?.used_web_search);
  const kbOk = Boolean(payload?.kb_sufficient);

  reportQueryEl.textContent = report.query || "";
  summaryEl.textContent = report.summary || "No summary returned.";
  confidenceEl.textContent = `confidence: ${report.confidence || "n/a"}`;

  cacheFlagEl.classList.toggle("hidden", !cached);
  webFlagEl.classList.toggle("hidden", !usedWeb);
  kbFlagEl.classList.toggle("hidden", !kbOk);

  findingsEl.innerHTML = "";
  const findings = report.key_findings || [];
  if (!findings.length) {
    findingsEl.innerHTML = "<li>No key findings.</li>";
  } else {
    for (const item of findings) {
      const li = document.createElement("li");
      li.textContent = item;
      findingsEl.appendChild(li);
    }
  }

  internalEl.innerHTML = "";
  const chunks = report.internal_context || [];
  if (!chunks.length) {
    internalEl.innerHTML = "<p class='meta'>No internal chunks retrieved.</p>";
  } else {
    for (const chunk of chunks) {
      const score =
        chunk.score === null || chunk.score === undefined
          ? ""
          : ` · score ${Number(chunk.score).toFixed(3)}`;
      internalEl.insertAdjacentHTML(
        "beforeend",
        `<div class="chunk">
          <span class="source">${escapeHtml(chunk.source || "knowledge_base")}${score}</span>
          <div>${escapeHtml(chunk.content || "")}</div>
        </div>`
      );
    }
  }

  externalEl.innerHTML = "";
  const hits = report.external_results || [];
  if (!hits.length) {
    externalEl.innerHTML = "<p class='meta'>No external MCP results.</p>";
  } else {
    for (const hit of hits) {
      const link = hit.url
        ? `<a href="${escapeHtml(hit.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(hit.url)}</a>`
        : "";
      externalEl.insertAdjacentHTML(
        "beforeend",
        `<div class="hit">
          <span class="title">${escapeHtml(hit.title || "Untitled")}</span>
          <div>${escapeHtml(hit.snippet || "")}</div>
          ${link}
        </div>`
      );
    }
  }

  taskMetaEl.textContent = `Task ID: ${taskId}`;
  reportEl.classList.remove("hidden");
}

async function pollTask(taskId) {
  while (true) {
    const response = await fetch(`/api/v1/task/${encodeURIComponent(taskId)}`);
    if (!response.ok) {
      throw new Error(`Status check failed (${response.status})`);
    }

    const data = await response.json();
    const status = data.status;

    if (status === "PENDING" || status === "STARTED" || status === "RETRY") {
      setBusy(true, `Status: ${status} — waiting for the worker…`);
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
      continue;
    }

    if (status === "FAILURE") {
      throw new Error(data.error || "Research task failed.");
    }

    if (status === "SUCCESS") {
      renderReport(taskId, data.result);
      setBusy(false, "Done.");
      return;
    }

    throw new Error(`Unexpected status: ${status}`);
  }
}

async function startResearch() {
  clearError();
  reportEl.classList.add("hidden");

  const query = queryEl.value.trim();
  if (!query) {
    showError("Enter a research question first.");
    return;
  }

  setBusy(true, "Queueing research…");

  try {
    const response = await fetch("/api/v1/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Could not start research (${response.status}): ${detail}`);
    }

    const accepted = await response.json();
    setBusy(true, `Queued · task ${accepted.task_id}`);
    await pollTask(accepted.task_id);
  } catch (error) {
    setBusy(false, "");
    showError(error.message || String(error));
  }
}

submitBtn.addEventListener("click", startResearch);
queryEl.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    startResearch();
  }
});
