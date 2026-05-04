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
