// PWA registration + update UX + install prompt.

import { initI18n, applyStaticTranslations, t } from "./i18n.js";

// 1. Khởi tạo i18n TRƯỚC khi apply static translations
await initI18n();
applyStaticTranslations(document);

// 2. Register service worker (chỉ HTTPS hoặc localhost)
if ("serviceWorker" in navigator) {
  try {
    const reg = await navigator.serviceWorker.register("./sw.js");

    // Phát hiện update: SW mới đang đợi
    reg.addEventListener("updatefound", () => {
      const nw = reg.installing;
      if (!nw) return;
      nw.addEventListener("statechange", () => {
        if (nw.state === "installed" && navigator.serviceWorker.controller) {
          showUpdateBanner(reg);
        }
      });
    });
  } catch (err) {
    console.warn("SW registration failed:", err);
  }
}

function showUpdateBanner(reg) {
  const banner = document.getElementById("update-banner");
  const btn = document.getElementById("reload-btn");
  if (!banner || !btn) return;
  banner.hidden = false;
  btn.addEventListener("click", () => {
    if (reg.waiting) {
      reg.waiting.postMessage("skipWaiting");
    }
    location.reload();
  }, { once: true });
}

// 3. Install prompt (Chrome/Edge PWA install)
let deferredPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;
  showInstallButton();
});

function showInstallButton() {
  // Chỉ thêm nếu chưa có
  if (document.getElementById("install-btn")) return;
  const btn = document.createElement("button");
  btn.id = "install-btn";
  btn.textContent = t("pwa.install") || "Install";
  btn.style.cssText = "position:fixed;bottom:16px;right:16px;z-index:40;" +
    "padding:8px 14px;border:none;border-radius:6px;" +
    "background:#8b4513;color:#fff;cursor:pointer;" +
    "box-shadow:0 2px 8px rgba(0,0,0,0.15);font-size:14px;";
  btn.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    btn.remove();
  });
  document.body.appendChild(btn);
}

// Offline/online indicator
function updateOnlineStatus() {
  const existing = document.getElementById("offline-indicator");
  if (navigator.onLine) {
    if (existing) existing.remove();
    return;
  }
  if (existing) return;
  const badge = document.createElement("div");
  badge.id = "offline-indicator";
  badge.textContent = t("pwa.offline_badge") || "Offline";
  badge.style.cssText = "position:fixed;top:12px;left:14px;z-index:45;" +
    "background:#b85c00;color:#fff;padding:4px 10px;border-radius:4px;" +
    "font-size:13px;box-shadow:0 2px 6px rgba(0,0,0,0.15);";
  document.body.appendChild(badge);
}
window.addEventListener("online", updateOnlineStatus);
window.addEventListener("offline", updateOnlineStatus);
updateOnlineStatus();
