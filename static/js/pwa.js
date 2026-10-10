(() => {
  const installButton = document.querySelector("#installAppButton");
  let installPrompt = null;
  let installCard = null;
  const DISMISS_KEY = "kidareh-install-dismissed-at";
  const DISMISS_FOR_MS = 7 * 24 * 60 * 60 * 1000;
  const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  const wasDismissedRecently = () => {
    try { const at = Number(localStorage.getItem(DISMISS_KEY) || 0); return at > 0 && Date.now() - at < DISMISS_FOR_MS; } catch { return false; }
  };
  function dismissCard() { if (installCard) installCard.hidden = true; try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch {} }
  function createInstallCard() {
    if (installCard) return installCard;
    installCard = document.createElement("aside");
    installCard.className = "pwa-install-card"; installCard.hidden = true; installCard.setAttribute("aria-label", "نصب اپ کی‌داره");
    installCard.innerHTML = `<span class="pwa-install-icon" aria-hidden="true">ک</span><div class="pwa-install-copy"><strong>کی‌داره همیشه دم دستت باشد</strong><p>برای دسترسی سریع‌تر، نسخهٔ اپ را به صفحهٔ اصلی گوشی اضافه کن.</p></div><button class="button button-primary pwa-install-action" type="button">نصب اپ</button><button class="pwa-install-close" type="button" aria-label="بعداً">×</button>`;
    document.body.appendChild(installCard);
    installCard.querySelector(".pwa-install-action").addEventListener("click", handleInstallClick);
    installCard.querySelector(".pwa-install-close").addEventListener("click", dismissCard);
    return installCard;
  }
  function showInstallHelp() {
    let help = document.querySelector("#pwaInstallHelp");
    if (!help) {
      help = document.createElement("dialog"); help.id = "pwaInstallHelp"; help.className = "pwa-install-help"; help.setAttribute("aria-labelledby", "pwaInstallHelpTitle");
      help.innerHTML = `<button class="pwa-help-close" type="button" aria-label="بستن">×</button><span class="pwa-install-icon" aria-hidden="true">ک</span><h2 id="pwaInstallHelpTitle">نصب کی‌داره روی گوشی</h2><p class="pwa-help-android"><strong>اندروید:</strong> منوی سه‌نقطهٔ مرورگر را باز کن و «Install app» یا «افزودن به صفحهٔ اصلی» را بزن.</p><p class="pwa-help-ios"><strong>آیفون:</strong> در Safari روی دکمهٔ اشتراک‌گذاری بزن و «Add to Home Screen» را انتخاب کن.</p><p class="pwa-help-generic"><strong>مرورگر:</strong> از منو گزینهٔ «افزودن به صفحهٔ اصلی» یا «نصب برنامه» را انتخاب کن.</p><button class="button button-primary pwa-help-done" type="button">متوجه شدم</button>`;
      document.body.appendChild(help);
      help.querySelectorAll(".pwa-help-close, .pwa-help-done").forEach(button => button.addEventListener("click", () => help.close()));
      help.addEventListener("click", event => { if (event.target === help) help.close(); });
    }
    const ua = navigator.userAgent || "";
    help.querySelector(".pwa-help-ios").hidden = !(/iPhone|iPad|iPod/i.test(ua));
    help.querySelector(".pwa-help-android").hidden = !(/Android/i.test(ua));
    help.querySelector(".pwa-help-generic").hidden = /iPhone|iPad|iPod|Android/i.test(ua);
    if (typeof help.showModal === "function") help.showModal(); else window.alert("از منوی مرورگر گزینهٔ «افزودن به صفحهٔ اصلی» را انتخاب کن.");
  }
  async function handleInstallClick() {
    if (!installPrompt) { showInstallHelp(); return; }
    installPrompt.prompt();
    try { const choice = await installPrompt.userChoice; if (choice?.outcome === "accepted") { if (installCard) installCard.hidden = true; if (installButton) installButton.hidden = true; } } catch {}
    installPrompt = null;
  }
  function maybeShowInstallCard() { if (isStandalone() || wasDismissedRecently()) return; createInstallCard().hidden = false; if (installButton) installButton.hidden = false; }
  window.addEventListener("beforeinstallprompt", event => { event.preventDefault(); installPrompt = event; if (installButton) installButton.hidden = false; });
  window.addEventListener("appinstalled", () => { if (installButton) installButton.hidden = true; if (installCard) installCard.hidden = true; installPrompt = null; });
  installButton?.addEventListener("click", handleInstallClick);
  async function checkSignedInAndOfferInstall() {
    if (isStandalone() || wasDismissedRecently()) return;
    try {
      const response = await fetch("/api/auth/me", { credentials: "same-origin", headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      if (data?.user) window.setTimeout(maybeShowInstallCard, 1800);
    } catch { /* Install is optional; network errors must not affect the page. */ }
  }
  checkSignedInAndOfferInstall();
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) window.addEventListener("load", () => navigator.serviceWorker.register("/static/sw.js").catch(() => {}));
})();