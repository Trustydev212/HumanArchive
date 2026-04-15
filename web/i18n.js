// Minimal i18n runtime — tải JSON từ web/i18n/<lang>.json và cung cấp
// hàm t(key, params?) để dùng trong app.js.

const STORAGE_KEY = "humanarchive.lang";
const DEFAULT_LANG = "vi";
const AVAILABLE = ["vi", "en", "fr"];

let _strings = {};
let _lang = DEFAULT_LANG;

function detectLang() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && AVAILABLE.includes(saved)) return saved;
  const nav = (navigator.language || "").toLowerCase();
  for (const code of AVAILABLE) {
    if (nav.startsWith(code)) return code;
  }
  return DEFAULT_LANG;
}

export async function initI18n() {
  _lang = detectLang();
  await loadLang(_lang);
  renderLangSwitcher();
}

async function loadLang(lang) {
  try {
    const res = await fetch(`i18n/${lang}.json`);
    _strings = await res.json();
    _lang = lang;
    document.documentElement.lang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
  } catch (err) {
    console.warn(`i18n: cannot load ${lang}`, err);
  }
}

export function t(key, params = null) {
  let s = _strings[key];
  if (s === undefined) return key; // fallback cho key thiếu
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      s = s.replaceAll(`{${k}}`, String(v));
    }
  }
  return s;
}

export function currentLang() { return _lang; }

function renderLangSwitcher() {
  let host = document.getElementById("lang-switcher");
  if (!host) {
    host = document.createElement("div");
    host.id = "lang-switcher";
    host.style.cssText = "position:fixed;top:12px;right:14px;z-index:50;display:flex;gap:6px;";
    document.body.appendChild(host);
  }
  host.innerHTML = AVAILABLE.map(lang => {
    const active = lang === _lang;
    return `<button data-lang="${lang}" style="
      border:1px solid #ccb;
      background:${active ? "#8b4513" : "#fff"};
      color:${active ? "#fff" : "#555"};
      padding:4px 10px;border-radius:4px;cursor:pointer;font-size:13px;
    ">${lang.toUpperCase()}</button>`;
  }).join("");
  host.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", async () => {
      await loadLang(btn.dataset.lang);
      // Reload để re-render tất cả strings
      location.reload();
    });
  });
}

// Convenience: replace text content của data-i18n elements
// <span data-i18n="events.no_match"></span>
export function applyStaticTranslations(root = document) {
  root.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-html]").forEach(el => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder));
  });
}
