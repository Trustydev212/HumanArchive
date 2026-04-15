// Form đóng góp ký ức — client-only. Không gửi dữ liệu đi đâu.
import { piiScrub } from "./hash_embed.js";

const $ = id => document.getElementById(id);

function newContributorId() {
  const hex = "0123456789abcdef";
  const bytes = crypto.getRandomValues(new Uint8Array(4));
  const a = Array.from(bytes.slice(0, 2), b => hex[b >> 4] + hex[b & 15]).join("");
  const b = Array.from(bytes.slice(2, 4), b => hex[b >> 4] + hex[b & 15]).join("");
  return `ha-${a}-${b}`;
}

function canonical(obj) {
  // JSON canonicalization khớp Python json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))
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

  if (!evName) errors.push("Tên sự kiện bắt buộc.");
  if (!evDate) errors.push("Ngày bắt buộc.");
  if (!role) errors.push("Chọn vai trò.");
  if (whatHappened.length < 20) errors.push("Mô tả phải ≥ 20 ký tự.");
  if (yourMotiv.length < 10) errors.push("Động cơ phải ≥ 10 ký tự (nguyên tắc 4).");

  if (errors.length) return { errors };

  // Build event_id: đơn giản, frontend không biết hash-collision-handling
  // ở server. Format: YYYY-<slug>-<4hex>
  const year = (evDate.match(/^\d{4}/) || [new Date().getFullYear()])[0];
  const slug = evName.toLowerCase()
    .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")  // strip diacritics
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "event";
  // hash 4 hex từ slug để ổn định
  // (async compute sau)

  const memory = {
    schema_version: "1.0",
    contributor_id: newContributorId(),
    submitted_at: new Date().toISOString(),
    event: {
      event_id: `${year}-${slug}-PENDING`,  // sẽ fill sau
      name: evName,
      date: evDate,
    },
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
  // Event hash
  const eventHash = (await sha256Hex(`${year}-${slug}`)).slice(0, 4);
  memory.event.event_id = `${year}-${slug}-${eventHash}`;
  // Memory hash (no memory_id field yet)
  const clone = JSON.parse(JSON.stringify(memory));
  delete clone.memory_id;
  memory.memory_id = (await sha256Hex(canonical(clone))).slice(0, 16);
  return memory;
}

function scanPII() {
  const fields = [
    ["Chuyện gì đã xảy ra", $("m-what").value],
    ["Chi tiết giác quan", $("m-sensory").value],
    ["Trạng thái cảm xúc", $("m-emotional").value],
    ["Động cơ", $("motiv-your").value],
    ["Áp lực bên ngoài", $("motiv-pressure").value],
    ["Nỗi sợ", $("motiv-fears").value],
    ["Hiểu thêm sau này", $("ctx-learned").value],
    ["Chọn lại", $("ctx-diff").value],
  ];
  const out = $("pii-result");
  out.innerHTML = "";
  let flagged = 0;
  fields.forEach(([name, val]) => {
    if (!val) return;
    const scrubbed = piiScrub(val);
    if (scrubbed !== val) {
      flagged++;
      const d = document.createElement("div");
      d.className = "trauma-warning";
      d.innerHTML = `<strong>${name}:</strong> có thể chứa PII. <br/>
        <span class="muted small">Phiên bản scrub gợi ý:</span><br/>
        <code style="white-space:pre-wrap">${escapeHtml(scrubbed)}</code>`;
      out.appendChild(d);
    }
  });
  if (!flagged) {
    out.textContent = "✓ Không phát hiện PII rõ ràng (chỉ kiểm tra cơ bản — bạn nên tự đọc lại lần nữa).";
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
}

$("btn-preview").addEventListener("click", preview);
$("btn-download").addEventListener("click", download);
$("btn-scan").addEventListener("click", scanPII);
