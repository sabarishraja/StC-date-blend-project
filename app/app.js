// app/app.js
const API_URL = "http://localhost:8001";

// ── Conversation history ──────────────────────────────────────
// Each entry: { role: "user"|"assistant", content: string }
let conversationHistory = [];

// ── Helpers ───────────────────────────────────────────────────

/** Auto-resize textarea as user types */
function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

/** Inject a clicked example question into the textarea */
function injectQuestion(el) {
  const ta = document.getElementById("question");
  ta.value = el.textContent.trim();
  autoResize(ta);
  ta.focus();
}

/** Scroll the chat thread to the bottom */
function scrollToBottom() {
  const thread = document.getElementById("chat-thread");
  thread.scrollTop = thread.scrollHeight;
}

/** Remove the empty-state placeholder on first message */
function hideEmptyState() {
  const empty = document.getElementById("empty-state");
  if (empty) empty.remove();
}

/** Clear the full conversation */
function clearConversation() {
  conversationHistory = [];
  const thread = document.getElementById("chat-thread");
  thread.innerHTML = `
    <div class="empty-state" id="empty-state">
      <div class="empty-icon">💬</div>
      <p class="empty-title">Ask anything about your analytics</p>
      <p class="empty-sub">Type a question below or pick one from the sidebar. You can ask follow-up questions naturally — the conversation is remembered.</p>
    </div>`;
}

// ── Markdown renderer (lightweight, no dependency) ────────────
/**
 * Converts the subset of markdown Claude commonly returns into HTML.
 * Handles: **bold**, *italic*, `code`, ### headings, - bullet lists, numbered lists, blank-line paragraphs.
 */
function renderMarkdown(text) {
  const lines = text.split("\n");
  const html = [];
  let inUl = false;
  let inOl = false;

  const closeList = () => {
    if (inUl) { html.push("</ul>"); inUl = false; }
    if (inOl) { html.push("</ol>"); inOl = false; }
  };

  const inlineFormat = (str) =>
    str
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");

  for (let raw of lines) {
    const line = raw.trimEnd();

    // Headings
    if (/^###\s+/.test(line)) {
      closeList();
      html.push(`<h4>${inlineFormat(line.replace(/^###\s+/, ""))}</h4>`);
      continue;
    }
    if (/^##\s+/.test(line)) {
      closeList();
      html.push(`<h3>${inlineFormat(line.replace(/^##\s+/, ""))}</h3>`);
      continue;
    }

    // Unordered list
    const ulMatch = line.match(/^[-*]\s+(.*)/);
    if (ulMatch) {
      if (inOl) { html.push("</ol>"); inOl = false; }
      if (!inUl) { html.push("<ul>"); inUl = true; }
      html.push(`<li>${inlineFormat(ulMatch[1])}</li>`);
      continue;
    }

    // Ordered list
    const olMatch = line.match(/^\d+\.\s+(.*)/);
    if (olMatch) {
      if (inUl) { html.push("</ul>"); inUl = false; }
      if (!inOl) { html.push("<ol>"); inOl = true; }
      html.push(`<li>${inlineFormat(olMatch[1])}</li>`);
      continue;
    }

    // Blank line → close lists, paragraph break
    if (line.trim() === "") {
      closeList();
      html.push(""); // will become paragraph separator
      continue;
    }

    // Regular paragraph line
    closeList();
    html.push(inlineFormat(line));
  }

  closeList();

  // Group consecutive non-tag lines into <p> blocks
  const joined = html.join("\n");
  const paragraphed = joined
    .split(/\n{2,}/)
    .map((block) => {
      block = block.trim();
      if (!block) return "";
      // Already a block-level tag
      if (/^<(ul|ol|li|h[234])/.test(block)) return block;
      return `<p>${block.replace(/\n/g, " ")}</p>`;
    })
    .filter(Boolean)
    .join("\n");

  return paragraphed;
}

// ── Source badge HTML ─────────────────────────────────────────
function sourceBadgesHTML(sources) {
  if (!sources || sources.length === 0) return "";
  return sources
    .map((s) => `<span class="answer-source-badge ${s}">${s}</span>`)
    .join("");
}

// ── Append a user bubble to the thread ───────────────────────
function appendUserBubble(text) {
  hideEmptyState();
  const row = document.createElement("div");
  row.className = "msg-row";
  row.innerHTML = `<div class="msg-user">${escapeHtml(text)}</div>`;
  document.getElementById("chat-thread").appendChild(row);
  scrollToBottom();
}

// ── Append an AI answer card to the thread ───────────────────
function appendAICard({ answer, sql, row_count, data_sources }) {
  const row = document.createElement("div");
  row.className = "msg-row";

  const badges = sourceBadgesHTML(data_sources);
  const rowCountLabel = row_count != null
    ? `<span class="answer-row-count">${row_count} row${row_count !== 1 ? "s" : ""}</span>`
    : "";

  row.innerHTML = `
    <div class="msg-ai">
      <div class="answer-meta">
        ${badges}
        ${rowCountLabel}
      </div>
      <div class="answer-body">${renderMarkdown(answer)}</div>
      <details class="sql-details">
        <summary>View SQL</summary>
        <pre>${escapeHtml(sql)}</pre>
      </details>
    </div>`;

  document.getElementById("chat-thread").appendChild(row);
  scrollToBottom();
}

/** Minimal HTML escaper to prevent XSS in user text / raw SQL */
function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Main ask function ─────────────────────────────────────────
async function askQuestion() {
  const ta = document.getElementById("question");
  const question = ta.value.trim();
  if (!question) return;

  const btn = document.getElementById("ask-btn");
  const thinkingBar = document.getElementById("thinking-bar");

  // Clear input, disable button, show thinking
  ta.value = "";
  ta.style.height = "auto";
  btn.disabled = true;
  thinkingBar.classList.remove("hidden");

  // Render user bubble immediately
  appendUserBubble(question);

  try {
    const resp = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        history: conversationHistory,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: "Unknown server error" }));
      throw new Error(err.detail || "Server error");
    }

    const data = await resp.json();

    // Append AI answer card
    appendAICard(data);

    // Update conversation history for next turn
    // We store the question as "user" and the plain answer text as "assistant"
    conversationHistory.push({ role: "user",      content: question });
    conversationHistory.push({ role: "assistant", content: data.answer });

  } catch (err) {
    // Show error as an AI card with no SQL
    appendAICard({
      answer: `⚠️ **Error:** ${err.message}`,
      sql: "",
      row_count: null,
      data_sources: [],
    });
  } finally {
    btn.disabled = false;
    thinkingBar.classList.add("hidden");
    ta.focus();
  }
}

// ── Keyboard shortcut ─────────────────────────────────────────
document.getElementById("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    askQuestion();
  }
});

// ── Load insights into sidebar ────────────────────────────────
async function loadInsights() {
  const list   = document.getElementById("insights-list");
  const status = document.getElementById("insights-status");

  try {
    const resp = await fetch(`${API_URL}/insights`);
    if (!resp.ok) throw new Error("Failed to load");
    const data = await resp.json();

    if (!data.insights || data.insights.length === 0) {
      status.textContent = "No insights — check server logs.";
      return;
    }

    status.textContent = "";
    list.innerHTML = data.insights.map((i) => `
      <div class="sidebar-insight ${i.type}">
        <div class="sidebar-insight-label">${escapeHtml(i.title)}</div>
        <div class="sidebar-insight-text">${escapeHtml(i.insight)}</div>
      </div>
    `).join("");
  } catch (err) {
    status.textContent = `Could not load: ${err.message}`;
  }
}

loadInsights();
