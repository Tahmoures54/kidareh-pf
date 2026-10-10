(() => {
  "use strict";

  const installButton = document.querySelector("#installAppButton");
  const DISMISS_KEY = "kidareh-install-dismissed-at";
  const DISMISS_FOR_MS = 7 * 24 * 60 * 60 * 1000;
  let installPrompt = null;
  let installCard = null;

  const isStandalone = () =>
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  const wasDismissedRecently = () => {
    try {
      const dismissedAt = Number(localStorage.getItem(DISMISS_KEY) || 0);
      return dismissedAt > 0 && Date.now() - dismissedAt < DISMISS_FOR_MS;
    } catch {
      return false;
    }
  };

  function dismissCard() {
    if (installCard) installCard.hidden = true;
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      // Storage may be unavailable in private browsing; dismissal still works for this view.
    }
  }

  function createInstallCard() {
    if (installCard) return installCard;

    installCard = document.createElement("aside");
    installCard.className = "pwa-install-card";
    installCard.hidden = true;
    installCard.setAttribute("aria-label", "نصب اپ کی‌داره");
    installCard.innerHTML = `
      <span class="pwa-install-icon" aria-hidden="true">ک</span>
      <div class="pwa-install-copy">
        <strong>کی‌داره همیشه دم دستت باشد</strong>
        <p>برای دسترسی سریع‌تر، نسخهٔ اپ را به صفحهٔ اصلی گوشی اضافه کن.</p>
      </div>
      <button class="button button-primary pwa-install-action" type="button">نصب اپ</button>
      <button class="pwa-install-close" type="button" aria-label="بعداً">×</button>`;

    document.body.appendChild(installCard);
    installCard.querySelector(".pwa-install-action").addEventListener("click", handleInstallClick);
    installCard.querySelector(".pwa-install-close").addEventListener("click", dismissCard);
    return installCard;
  }

  function showInstallHelp() {
    let help = document.querySelector("#pwaInstallHelp");
    if (!help) {
      help = document.createElement("dialog");
      help.id = "pwaInstallHelp";
      help.className = "pwa-install-help";
      help.setAttribute("aria-labelledby", "pwaInstallHelpTitle");
      help.innerHTML = `
        <button class="pwa-help-close" type="button" aria-label="بستن">×</button>
        <span class="pwa-install-icon" aria-hidden="true">ک</span>
        <h2 id="pwaInstallHelpTitle">نصب کی‌داره روی گوشی</h2>
        <p class="pwa-help-android"><strong>اندروید:</strong> منوی سه‌نقطهٔ مرورگر را باز کن و «Install app» یا «افزودن به صفحهٔ اصلی» را بزن.</p>
        <p class="pwa-help-ios"><strong>آیفون:</strong> در Safari روی دکمهٔ اشتراک‌گذاری بزن و «Add to Home Screen» را انتخاب کن.</p>
        <p class="pwa-help-generic"><strong>مرورگر:</strong> از منو گزینهٔ «افزودن به صفحهٔ اصلی» یا «نصب برنامه» را انتخاب کن.</p>
        <button class="button button-primary pwa-help-done" type="button">متوجه شدم</button>`;
      document.body.appendChild(help);
      help.querySelectorAll(".pwa-help-close, .pwa-help-done").forEach(button => {
        button.addEventListener("click", () => help.close());
      });
      help.addEventListener("click", event => {
        if (event.target === help) help.close();
      });
      help.addEventListener("keydown", event => {
        if (event.key === "Escape") help.close();
      });
    }

    const ua = navigator.userAgent || "";
    const isIOS = /iPhone|iPad|iPod/i.test(ua);
    const isAndroid = /Android/i.test(ua);
    help.querySelector(".pwa-help-ios").hidden = !isIOS;
    help.querySelector(".pwa-help-android").hidden = !isAndroid;
    help.querySelector(".pwa-help-generic").hidden = isIOS || isAndroid;

    if (typeof help.showModal === "function") help.showModal();
    else window.alert("از منوی مرورگر گزینهٔ «افزودن به صفحهٔ اصلی» را انتخاب کن.");
  }

  async function handleInstallClick() {
    if (!installPrompt) {
      showInstallHelp();
      return;
    }

    try {
      await installPrompt.prompt();
      const choice = await installPrompt.userChoice;
      if (choice && choice.outcome === "accepted") {
        if (installCard) installCard.hidden = true;
        if (installButton) installButton.hidden = true;
      }
    } catch {
      showInstallHelp();
    } finally {
      installPrompt = null;
    }
  }

  function maybeShowInstallCard() {
    if (isStandalone() || wasDismissedRecently()) return;
    createInstallCard().hidden = false;
    if (installButton) installButton.hidden = false;
  }

  function markCurrentMobileNav() {
    const path = window.location.pathname.replace(/\/$/, "") || "/";
    document.querySelectorAll(".mobile-nav-item").forEach(link => {
      const href = link.getAttribute("href") || "";
      const target = href.split("#")[0].replace(/\/$/, "") || "/";
      const isCurrent = target === path || (target === "/" && path === "/");
      if (isCurrent) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  window.addEventListener("beforeinstallprompt", event => {
    // Keep the native prompt until the signed-in user sees the install offer.
    event.preventDefault();
    installPrompt = event;
  });

  window.addEventListener("appinstalled", () => {
    if (installButton) installButton.hidden = true;
    if (installCard) installCard.hidden = true;
    installPrompt = null;
  });

  installButton?.addEventListener("click", handleInstallClick);
  markCurrentMobileNav();

  async function checkSignedInAndOfferInstall() {
    if (isStandalone() || wasDismissedRecently()) return;
    try {
      const response = await fetch("/api/auth/me", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store"
      });
      if (!response.ok) return;
      const data = await response.json();
      if (data && data.user) window.setTimeout(maybeShowInstallCard, 1800);
    } catch {
      // Installation is optional and must never block page usage.
    }
  }

  checkSignedInAndOfferInstall();

  if ("serviceWorker" in navigator &&
      (location.protocol === "https:" || location.hostname === "localhost")) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" })
        .then(registration => registration.update())
        .catch(() => {
          // The site remains usable when service-worker installation is unavailable.
        });
    });
  }
})();