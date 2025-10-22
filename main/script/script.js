const apiBase = "http://localhost:5000/noticias";
const grid = document.getElementById("grid");
const statusBox = document.getElementById("status");
const btn = document.getElementById("refresh");
const limitInput = document.getElementById("limit");

function fmtDate(dateStr) {
  return dateStr && dateStr.trim() ? dateStr : "—"; 
}

function makeCard(item) {
  const card = document.createElement("article");
  card.className = "card";

  const badge = document.createElement("div");
  badge.className = "badge" + (item.featured ? " featured" : "");
  badge.textContent = item.featured ? "FEATURADO" : "Card";

  const h3 = document.createElement("h3");
  h3.className = "title";
  const a = document.createElement("a");
  a.href = item.href;
  a.target = "_blank";
  a.rel = "noopener";
  a.textContent = item.title || "(sem título)";
  h3.appendChild(a);

  const subtitle = document.createElement("p");
  subtitle.className = "subtitle";
  subtitle.textContent = item.subtitle || "";

  const meta = document.createElement("div");
  meta.className = "meta";
  let host = "";
  try { host = new URL(item.href).hostname.replace(/^www\./,''); } catch {}
  meta.innerHTML = `
    <span>Data: <strong>${fmtDate(item.createdAt)}</strong></span>
    <span>Fonte: <strong>${host}</strong></span>`;

  card.appendChild(badge);
  card.appendChild(h3);
  if (item.subtitle) card.appendChild(subtitle);
  card.appendChild(meta);
  return card;
}

async function load() {
  grid.innerHTML = "";
  statusBox.className = "empty loading";
  statusBox.textContent = "Carregando…";

  try {
    const params = new URLSearchParams();
    const url = params.toString() ? `${apiBase}?${params}` : apiBase;
    const res = await fetch(url, { headers: { "Accept": "application/json" } });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      statusBox.className = "empty";
      statusBox.textContent = "Nenhum card encontrado.";
      return;
    }

    statusBox.textContent = "";
    statusBox.className = "empty";
    data.forEach(item => grid.appendChild(makeCard(item)));
  } catch (err) {
    statusBox.className = "error";
    statusBox.textContent = `Falha ao carregar: ${err.message || err}`;
  }
}

btn.addEventListener("click", load);
