// HumanArchive web browser — vanilla JS, no build.
// Reads archive/graph.json and archive/rag_index.json, performs client-side
// RAG search using a JS-port of HashEmbedder (matching Python byte-for-byte).

import { hashEmbed, piiScrub, cosineSim } from "./hash_embed.js";
import { t } from "./i18n.js";

const GRAPH_URL = "../archive/graph.json";
const RAG_URL = "../archive/rag_index.json";

let GRAPH = null;
let RAG = null;

// Đợi pwa.js hoàn tất initI18n trước khi render
// (pwa.js chạy trước trong HTML và await initI18n)
window.addEventListener("load", boot);

async function boot() {
  // Graph
  try {
    const r = await fetch(GRAPH_URL);
    GRAPH = await r.json();
    renderOverview();
    renderEvents();
    renderMermaid();
    renderCategoryTree();
    renderTagCloud();
  } catch (err) {
    document.getElementById("overview-stats").innerHTML = t("overview.load_error_html");
  }
  // RAG
  try {
    const r = await fetch(RAG_URL);
    RAG = await r.json();
    document.getElementById("rag-status").textContent = t("search.index_ready", {
      n: RAG.entries.length,
      embedder: RAG.embedder_name,
      dim: RAG.dim,
    });
  } catch (err) {
    document.getElementById("rag-status").textContent = t("search.index_missing");
  }

  wireSearch();
  wireFilters();

  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false, theme: "neutral" });
  }
}

// ----------------------------- Overview ------------------------------
function renderOverview() {
  const n = GRAPH.nodes.length;
  const memCount = GRAPH.nodes.reduce((a, x) => a + x.memory_count, 0);
  const edgeCount = GRAPH.edges.length;
  const roleCount = new Set(GRAPH.nodes.flatMap(n => n.roles_present)).size;
  document.getElementById("overview-stats").innerHTML = `
    <div class="stat"><b>${n}</b><span>${t("stats.events")}</span></div>
    <div class="stat"><b>${memCount}</b><span>${t("stats.memories")}</span></div>
    <div class="stat"><b>${edgeCount}</b><span>${t("stats.edges")}</span></div>
    <div class="stat"><b>${roleCount}</b><span>${t("stats.roles")}</span></div>
    <div class="stat"><b>${Object.keys(GRAPH.tag_counts).length}</b><span>${t("stats.tags")}</span></div>
  `;
}

// ----------------------------- Events --------------------------------
let eventQuery = "", eventCat = "", eventRole = "";

function renderEvents() {
  const list = document.getElementById("event-list");
  list.innerHTML = "";

  const catSel = document.getElementById("filter-category");
  if (catSel.options.length <= 1) {
    const cats = new Set();
    GRAPH.nodes.forEach(n => n.categories.forEach(c => cats.add(c)));
    [...cats].sort().forEach(c => {
      const o = document.createElement("option");
      o.value = c; o.textContent = c;
      catSel.appendChild(o);
    });
  }

  const q = eventQuery.toLowerCase();
  const filtered = GRAPH.nodes.filter(n => {
    if (eventCat && !n.categories.includes(eventCat)) return false;
    if (eventRole && !n.roles_present.includes(eventRole)) return false;
    if (q) {
      const hay = (n.name + " " + n.tags.join(" ") + " " + n.categories.join(" ")).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  if (!filtered.length) {
    list.innerHTML = `<p class='muted'>${t("events.no_match")}</p>`;
    return;
  }

  filtered.forEach(n => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <h3>${escapeHtml(n.name)}</h3>
      <div class="meta">${escapeHtml(n.date)} · ${n.memory_count} ${t("events.memories_count")} · ${n.roles_present.length} ${t("events.perspectives_count")}</div>
      <div>${n.roles_present.map(r => `<span class="role-badge">${r}</span>`).join("")}</div>
      <div class="tags">${n.tags.map(tg => `<span class="tag">#${escapeHtml(tg)}</span>`).join("")}</div>
    `;
    card.addEventListener("click", () => openEventModal(n));
    list.appendChild(card);
  });
}

function wireFilters() {
  document.getElementById("search-events").addEventListener("input", e => {
    eventQuery = e.target.value; renderEvents();
  });
  document.getElementById("filter-category").addEventListener("change", e => {
    eventCat = e.target.value; renderEvents();
  });
  document.getElementById("filter-role").addEventListener("change", e => {
    eventRole = e.target.value; renderEvents();
  });
}

function openEventModal(n) {
  const host = document.getElementById("detail-modal-host");
  host.innerHTML = `
    <div class="modal-bg">
      <div class="modal">
        <button class="close">&times;</button>
        <h2>${escapeHtml(n.name)}</h2>
        <p class="muted">${t("modal.event_id")}: <code>${n.event_id}</code></p>
        <ul>
          <li><strong>${t("modal.date")}:</strong> ${escapeHtml(n.date || t("modal.no_date"))}</li>
          <li><strong>${t("modal.location")}:</strong> ${escapeHtml(n.location || t("modal.no_location"))}</li>
          <li><strong>${t("modal.categories")}:</strong> ${n.categories.length ? n.categories.join(", ") : t("modal.no_categories")}</li>
          <li><strong>${t("modal.tags")}:</strong> ${n.tags.map(tg => `#${tg}`).join(", ") || t("modal.no_tags")}</li>
          <li><strong>${t("modal.roles_present")}:</strong> ${n.roles_present.join(", ")}</li>
          <li><strong>${t("modal.memory_count")}:</strong> ${n.memory_count}</li>
        </ul>
        <p class="muted small">${t("modal.hint")}</p>
      </div>
    </div>`;
  host.querySelector(".close").onclick = () => host.innerHTML = "";
  host.querySelector(".modal-bg").onclick = e => {
    if (e.target.classList.contains("modal-bg")) host.innerHTML = "";
  };
}

// ----------------------------- Graph ---------------------------------
function renderMermaid() {
  const relMap = {
    "part_of": "-.->|part_of|",
    "caused_by": "-->|caused_by|",
    "led_to": "-->|led_to|",
    "happened_during": "-.->|during|",
    "contradicts": "-.->|contradicts|",
    "corroborates": "-->|corroborates|",
    "aftermath_of": "-->|aftermath_of|",
    "related": "-.->|related|",
  };
  const lines = ["graph LR"];
  const nodeId = eid => "E_" + eid.replace(/-/g, "_");
  GRAPH.nodes.forEach(n => {
    const safe = n.name.replace(/"/g, "'");
    lines.push(`  ${nodeId(n.event_id)}["${safe}<br/>(${n.date})<br/>n=${n.memory_count}"]`);
  });
  GRAPH.edges.forEach(e => {
    const arrow = relMap[e.type] || "-->";
    lines.push(`  ${nodeId(e.source)} ${arrow} ${nodeId(e.target)}`);
  });

  const host = document.getElementById("mermaid-graph");
  host.innerHTML = "";
  const div = document.createElement("div");
  div.className = "mermaid";
  div.textContent = lines.join("\n");
  host.appendChild(div);
  if (window.mermaid) window.mermaid.run({ nodes: [div] });
}

function renderCategoryTree() {
  const host = document.getElementById("category-tree");
  const names = Object.fromEntries(GRAPH.nodes.map(n => [n.event_id, n.name]));
  function walk(tree) {
    const ul = document.createElement("ul");
    Object.entries(tree).sort().forEach(([k, v]) => {
      const li = document.createElement("li");
      if (Array.isArray(v)) {
        li.innerHTML = `<strong>${escapeHtml(k)}</strong> <span class="count">(${v.length})</span>`;
        const sub = document.createElement("ul");
        v.forEach(eid => {
          const sli = document.createElement("li");
          sli.innerHTML = `<code>${eid}</code> — ${escapeHtml(names[eid] || eid)}`;
          sub.appendChild(sli);
        });
        li.appendChild(sub);
      } else {
        li.innerHTML = `<strong>${escapeHtml(k)}/</strong>`;
        li.appendChild(walk(v));
      }
      ul.appendChild(li);
    });
    return ul;
  }
  host.innerHTML = "";
  host.appendChild(walk(GRAPH.category_tree || {}));
}

function renderTagCloud() {
  const host = document.getElementById("tag-cloud");
  host.innerHTML = "";
  Object.entries(GRAPH.tag_counts).forEach(([tag, n]) => {
    const size = 0.8 + Math.min(n / 3, 1.2);
    const span = document.createElement("span");
    span.className = "tag";
    span.style.fontSize = size + "rem";
    span.textContent = `#${tag} (${n})`;
    host.appendChild(span);
  });
}

// ----------------------------- RAG search ----------------------------
function wireSearch() {
  document.getElementById("rag-form").addEventListener("submit", async e => {
    e.preventDefault();
    if (!RAG) { alert(t("search.index_not_loaded")); return; }
    const q = document.getElementById("rag-query").value.trim();
    if (!q) return;
    await doSearch(q);
  });
}

async function doSearch(rawQuery) {
  const out = document.getElementById("rag-results");
  const status = document.getElementById("rag-status");

  const scrubbed = piiScrub(rawQuery);
  if (RAG.embedder_name !== "HashEmbedder") {
    status.innerHTML = t("search.incompatible_embedder_html", { embedder: RAG.embedder_name });
    out.innerHTML = "";
    return;
  }
  const qvec = await hashEmbed(scrubbed, RAG.dim);

  const scored = RAG.entries.map(e => ({ e, score: cosineSim(qvec, e.embedding) }));
  scored.sort((a, b) => b.score - a.score);

  const seenRoles = new Set(), picked = [], remaining = [];
  for (const s of scored) {
    if (!seenRoles.has(s.e.role)) {
      picked.push(s); seenRoles.add(s.e.role);
      if (picked.length >= 5) break;
    } else {
      remaining.push(s);
    }
  }
  for (const s of remaining) {
    if (picked.length >= 5) break;
    picked.push(s);
  }

  status.textContent = t("search.query_scrubbed", { q: scrubbed, n: picked.length });
  out.innerHTML = "";
  picked.forEach((s, i) => {
    const d = document.createElement("div");
    d.className = "hit";
    d.innerHTML = `
      <div class="hit-meta">
        [${i + 1}] <span class="role-badge">${s.e.role}</span>
        event: <code>${s.e.event_id}</code> ·
        memory: <code>${s.e.memory_id.slice(0,10)}…</code> ·
        score: ${s.score.toFixed(3)}
      </div>
      <pre>${escapeHtml(s.e.text_scrubbed)}</pre>
    `;
    out.appendChild(d);
  });

  if (!picked.length) {
    out.innerHTML = `<p class="muted">${t("search.no_hits")}</p>`;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
