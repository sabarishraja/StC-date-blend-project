const API_BASE = window.location.origin.includes("localhost") || window.location.origin.includes("127.0.0.1")
  ? "http://localhost:8001"
  : window.location.origin;

let fsFile = null;
let msFiles = [];

function getPassword() {
  let pw = sessionStorage.getItem("uploadPassword");
  if (!pw) {
    pw = prompt("Enter the upload password:");
    if (pw) sessionStorage.setItem("uploadPassword", pw);
  }
  return pw;
}

function clearPassword() {
  sessionStorage.removeItem("uploadPassword");
}

function setupDropzone(zoneId, inputId, isMulti, onFiles) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);

  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragging"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragging"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragging");
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.endsWith(".csv"));
    onFiles(isMulti ? files : files.slice(0, 1));
  });
  input.addEventListener("change", () => {
    const files = Array.from(input.files);
    onFiles(isMulti ? files : files.slice(0, 1));
  });
}

setupDropzone("fs-dropzone", "fs-input", false, (files) => {
  fsFile = files[0] || null;
  document.getElementById("fs-file").textContent = fsFile ? fsFile.name : "";
  document.getElementById("fs-upload-btn").disabled = !fsFile;
});

setupDropzone("ms-dropzone", "ms-input", true, (files) => {
  msFiles = files.slice(0, 3);
  const ul = document.getElementById("ms-files");
  ul.innerHTML = "";
  msFiles.forEach(f => {
    const li = document.createElement("li");
    li.textContent = f.name;
    ul.appendChild(li);
  });
  document.getElementById("ms-upload-btn").disabled = msFiles.length === 0;
});

async function postFiles(endpoint, formData) {
  const pw = getPassword();
  if (!pw) return null;
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "X-Upload-Password": pw },
    body: formData,
  });
  if (res.status === 401) {
    clearPassword();
    alert("Wrong password. Try again.");
    return null;
  }
  return res;
}

function renderResults(results) {
  const card = document.getElementById("results-card");
  const ul = document.getElementById("results-list");
  card.hidden = false;
  results.forEach(r => {
    const li = document.createElement("li");
    li.className = r.ok ? "result-ok" : "result-err";
    if (r.ok) {
      const range = r.date_range ? `${r.date_range[0]} → ${r.date_range[1]}` : "";
      li.innerHTML = `<span class="result-icon">✓</span> <strong>${r.filename}</strong> — ${r.table} — ${r.rows_written} rows ${range ? `(${range})` : ""}`;
    } else {
      li.innerHTML = `<span class="result-icon">✗</span> <strong>${r.filename}</strong> — ${r.errors.join("; ")}`;
    }
    ul.appendChild(li);
  });
}

async function uploadFullstory() {
  if (!fsFile) return;
  const btn = document.getElementById("fs-upload-btn");
  btn.disabled = true;
  btn.textContent = "Uploading…";
  try {
    const fd = new FormData();
    fd.append("file", fsFile);
    const res = await postFiles("/upload/fullstory", fd);
    if (!res) return;
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      renderResults([{ ok: false, filename: fsFile.name, errors: [err.detail || `HTTP ${res.status}`] }]);
      return;
    }
    const data = await res.json();
    renderResults(data.results);
    fsFile = null;
    document.getElementById("fs-file").textContent = "";
    document.getElementById("fs-input").value = "";
  } catch (e) {
    renderResults([{ ok: false, filename: fsFile?.name || "file", errors: [String(e)] }]);
  } finally {
    btn.textContent = "Upload to Supabase";
    btn.disabled = !fsFile;
  }
}

async function uploadMeilisearch() {
  if (!msFiles.length) return;
  const btn = document.getElementById("ms-upload-btn");
  btn.disabled = true;
  btn.textContent = "Uploading…";
  try {
    const fd = new FormData();
    msFiles.forEach(f => fd.append("files", f));
    const res = await postFiles("/upload/meilisearch", fd);
    if (!res) return;
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      renderResults(msFiles.map(f => ({ ok: false, filename: f.name, errors: [err.detail || `HTTP ${res.status}`] })));
      return;
    }
    const data = await res.json();
    renderResults(data.results);
    msFiles = [];
    document.getElementById("ms-files").innerHTML = "";
    document.getElementById("ms-input").value = "";
  } catch (e) {
    renderResults([{ ok: false, filename: "meilisearch upload", errors: [String(e)] }]);
  } finally {
    btn.textContent = "Upload to Supabase";
    btn.disabled = msFiles.length === 0;
  }
}
