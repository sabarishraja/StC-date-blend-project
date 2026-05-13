// app/app.js
const API_URL = "http://localhost:8000";

function setQuestion(el) {
  document.getElementById("question").value = el.textContent.trim();
}

async function askQuestion() {
  const question = document.getElementById("question").value.trim();
  if (!question) return;

  const btn = document.getElementById("ask-btn");
  const status = document.getElementById("status");
  const result = document.getElementById("result");

  btn.disabled = true;
  status.textContent = "Thinking...";
  status.classList.remove("hidden");
  result.classList.add("hidden");

  try {
    const resp = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Server error");
    }

    const data = await resp.json();

    document.getElementById("answer").textContent = data.answer;
    document.getElementById("sql-output").textContent = data.sql;
    result.classList.remove("hidden");
    status.classList.add("hidden");
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) askQuestion();
});

async function loadInsights() {
  const grid = document.getElementById("insights-grid");
  const status = document.getElementById("insights-status");
  try {
    const resp = await fetch(`${API_URL}/insights`);
    if (!resp.ok) throw new Error("Failed to load");
    const data = await resp.json();
    if (!data.insights || data.insights.length === 0) {
      status.textContent = "No insights returned — check server logs or visit /debug/queries.";
      return;
    }
    status.textContent = "";
    grid.innerHTML = data.insights.map(i => `
      <div class="insight-card ${i.type}">
        <div class="insight-card-title">${i.title}</div>
        <div class="insight-card-text">${i.insight}</div>
      </div>
    `).join("");
  } catch (err) {
    status.textContent = `Could not load insights: ${err.message}`;
  }
}

loadInsights();
