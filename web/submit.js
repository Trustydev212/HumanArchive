// Form đóng góp ký ức — client-only, không gửi data đi đâu.
// Thêm localStorage draft persistence + i18n.
import { piiScrub } from "./hash_embed.js";
import { t } from "./i18n.js";

const $ = id => document.getElementById(id);
const DRAFT_KEY = "humanarchive.submit.draft";

const FORM_FIELDS = [
  "ev-name", "ev-date", "ev-location", "ev-tags", "ev-categories",
  "p-role", "p-proximity", "p-age",
  "m-what", "m-sensory", "m-emotional",
  "motiv-your", "motiv-pressure", "motiv-fears",
  "ctx-learned", "ctx-diff",
  "c-embargo",
];

// --------------------------------------------------------------------------
// Draft persistence (offline-friendly)
// --------------------------------------------------------------------------

function saveDraft() {
  const draft = {};
  FORM_FIELDS.forEach(id => {
    const el = $(id);
    if (el) draft[id] = el.value;
  });
  draft._public = $("c-public").checked;
  draft._ai = $("c-ai").checked;
  draft._saved_at = new Date().toISOString();
  localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  const indicator = $("draft-indicator");
  if (indicator) indicator.hidden = false;
}

function loadDraft() {
  const raw = localStorage.getItem(DRAFT_KEY);
  if (!raw) return false;
  try {
    const draft = JSON.parse(raw);
    FORM_FIELDS.forEach(id => {
      const el = $(id);
      if (el && draft[id] !== undefined) el.value = draft[id];
    });
    if (draft._public !== undefined) $("c-public").checked = draft._public;
    if (draft._ai !== undefined) $("c-ai").checked = draft._ai;
    const indicator = $("draft-indicator");
    if (indicator) indicator.hidden = false;
    return true;
  } catch (e) {
    return false;
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY);
  FORM_FIELDS.forEach(id => {
    const el = $(id);
    if (!el) return;
    if (el.type === "checkbox") el.checked = false;
    else el.value = "";
  });
  $("c-public").checked = true;
  $("c-ai").checked = true;
  const indicator = $("draft-indicator");
  if (indicator) indicator.hidden = true;
}

function wireDraftAutoSave() {
  let timer = null;
  const onInput = () => {
    clearTimeout(timer);
    timer = setTimeout(saveDraft, 500);  // debounce
  };
  FORM_FIELDS.forEach(id => {
    const el = $(id);
    if (el) el.addEventListener("input", onInput);
  });
  $("c-public").addEventListener("change", onInput);
  $("c-ai").addEventListener("change", onInput);
}

// --------------------------------------------------------------------------
// Build + validate
// --------------------------------------------------------------------------

function newContributorId() {
  const hex = "0123456789abcdef";
  const bytes = crypto.getRandomValues(new Uint8Array(4));
  const a = Array.from(bytes.slice(0, 2), b => hex[b >> 4] + hex[b & 15]).join("");
  const b = Array.from(bytes.slice(2, 4), b => hex[b >> 4] + hex[b & 15]).join("");
  return `ha-${a}-${b}`;
}

function canonical(obj) {
  if (obj === null || typeof obj !== "object") return JSON.stringify(obj);
  if (Array.isArray(obj)) return "[" + obj.map(canonical).join(",") + "]";
  const keys = Object.keys(obj).sort();
  return "{" + keys.map(k => JSON.stringify(k) + ":" + canonical(obj[k])).join(",") + "}";
}

async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, "0")).join("");
}

function parseList(str) {
  if (!str) return undefined;
  const arr = str.split(",").map(s => s.trim()).filter(Boolean);
  return arr.length ? arr : undefined;
}

function addIfNonEmpty(obj, key, val) {
  if (val === undefined || val === null) return;
  if (typeof val === "string" && !val.trim()) return;
  obj[key] = val;
}

function buildMemory() {
  const errors = [];
  const evName = $("ev-name").value.trim();
  const evDate = $("ev-date").value.trim();
  const role = $("p-role").value;
  const whatHappened = $("m-what").value.trim();
  const yourMotiv = $("motiv-your").value.trim();

  if (!evName) errors.push(t("submit.field.event_name").replace(" *", "") + ": required");
  if (!evDate) errors.push(t("submit.field.event_date").replace(" *", "") + ": required");
  if (!role) errors.push(t("submit.field.role").replace(" *", "") + ": required");
  if (whatHappened.length < 20) errors.push("what_happened: min 20 chars");
  if (yourMotiv.length < 10) errors.push("motivation.your_motivation: min 10 chars (principle 4)");

  if (errors.length) return { errors };

  const year = (evDate.match(/^\d{4}/) || [new Date().getFullYear()])[0];
  const slug = evName.toLowerCase()
    .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "event";

  const memory = {
    schema_version: "1.0",
    contributor_id: newContributorId(),
    submitted_at: new Date().toISOString(),
    event: { event_id: `${year}-${slug}-PENDING`, name: evName, date: evDate },
    perspective: { role },
    memory: { what_happened: whatHappened },
    motivation: { your_motivation: yourMotiv },
    context: {},
    consent: {
      public: $("c-public").checked,
      embargo_until: $("c-embargo").value || null,
      withdrawn: false,
      allow_ai_analysis: $("c-ai").checked,
    },
    language: "vi",
  };

  addIfNonEmpty(memory.event, "location", $("ev-location").value.trim());
  addIfNonEmpty(memory.event, "tags", parseList($("ev-tags").value));
  addIfNonEmpty(memory.event, "categories", parseList($("ev-categories").value));
  addIfNonEmpty(memory.perspective, "proximity", $("p-proximity").value);
  const age = parseInt($("p-age").value, 10);
  if (!Number.isNaN(age)) memory.perspective.age_at_event = age;
  addIfNonEmpty(memory.memory, "sensory_details", $("m-sensory").value.trim());
  addIfNonEmpty(memory.memory, "emotional_state", $("m-emotional").value.trim());
  addIfNonEmpty(memory.motivation, "external_pressure", $("motiv-pressure").value.trim());
  addIfNonEmpty(memory.motivation, "fears_at_the_time", $("motiv-fears").value.trim());
  addIfNonEmpty(memory.context, "what_learned_after", $("ctx-learned").value.trim());
  addIfNonEmpty(memory.context, "would_do_differently", $("ctx-diff").value.trim());

  return { memory, slug, year };
}

async function computeIds(result) {
  const { memory, slug, year } = result;
  const eventHash = (await sha256Hex(`${year}-${slug}`)).slice(0, 4);
  memory.event.event_id = `${year}-${slug}-${eventHash}`;
  const clone = JSON.parse(JSON.stringify(memory));
  delete clone.memory_id;
  memory.memory_id = (await sha256Hex(canonical(clone))).slice(0, 16);
  return memory;
}

function scanPII() {
  const fieldMap = [
    ["submit.field.what_happened", $("m-what").value],
    ["submit.field.sensory", $("m-sensory").value],
    ["submit.field.emotional", $("m-emotional").value],
    ["submit.field.your_motivation", $("motiv-your").value],
    ["submit.field.pressure", $("motiv-pressure").value],
    ["submit.field.fears", $("motiv-fears").value],
    ["submit.field.learned", $("ctx-learned").value],
    ["submit.field.different", $("ctx-diff").value],
  ];
  const out = $("pii-result");
  out.innerHTML = "";
  let flagged = 0;
  fieldMap.forEach(([key, val]) => {
    if (!val) return;
    const scrubbed = piiScrub(val);
    if (scrubbed !== val) {
      flagged++;
      const d = document.createElement("div");
      d.className = "trauma-warning";
      const label = t(key).replace(" *", "");
      d.innerHTML = `<strong>${escapeHtml(label)}:</strong> có thể chứa PII.<br/>
        <span class="muted small">${t("submit.pii.found_suffix")}</span><br/>
        <code style="white-space:pre-wrap">${escapeHtml(scrubbed)}</code>`;
      out.appendChild(d);
    }
  });
  if (!flagged) {
    out.textContent = t("submit.pii.none");
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

async function preview() {
  $("errors").textContent = "";
  const r = buildMemory();
  if (r.errors) {
    $("errors").innerHTML = r.errors.map(e => "• " + escapeHtml(e)).join("<br>");
    $("json-preview").style.display = "none";
    return null;
  }
  const mem = await computeIds(r);
  const pre = $("json-preview");
  pre.style.display = "block";
  pre.textContent = JSON.stringify(mem, null, 2);
  return mem;
}

async function download() {
  const mem = await preview();
  if (!mem) return;
  const blob = new Blob([JSON.stringify(mem, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${mem.memory_id}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
  // Không clear draft tự động — user có thể muốn giữ để sửa
}

// Wire up sau khi load (pwa.js đã init i18n)
window.addEventListener("load", () => {
  loadDraft();
  wireDraftAutoSave();
  $("btn-preview").addEventListener("click", preview);
  $("btn-download").addEventListener("click", download);
  $("btn-scan").addEventListener("click", scanPII);
  const clearBtn = $("draft-clear");
  if (clearBtn) clearBtn.addEventListener("click", () => {
    if (confirm("Xoá draft và reset form?")) clearDraft();
  });
});
