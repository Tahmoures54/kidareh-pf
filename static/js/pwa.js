/* کی‌داره — PWA: بنر نصب هوشمند، راهنمای iOS، ثبت Service Worker و اعلان نسخهٔ جدید */
(() => {
  "use strict";

  const Rules = window.KidarehPwaRules;
  const UI = window.KidarehUI;
  if (!Rules || !UI) return;

  const DISMISS_KEY = "kidareh-install-dismissed-at";
  const UPDATED_KEY = "kidareh-just-updated";
  const EVENTS_KEY = "kidareh-pwa-events";
  const pageLoadedAt = Date.now();

  let installPrompt = null;
  let banner = null;
  let engagementShown = false;

  const isStandalone = () =>
    window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

  function readDismissedAt() {
    try { return Number(localStorage.getItem(DISMISS_KEY) || 0); } catch { return 0; }
  }

  function dismiss() {
    try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch { /* private mode */ }
    if (banner) banner.hidden = true;
  }

  // Analytics: رویدادها به dataLayer (اگر وجود داشته باشد) و یک CustomEvent ارسال می‌شوند.
  function track(name, detail = {}) {
    const payload = { event: name, ...detail, at: new Date().toISOString() };
    if (Array.isArray(window.dataLayer)) window.dataLayer.push(payload);
    window.dispatchEvent(new CustomEvent("kidareh:analytics", { detail: payload }));
  }

  function createBanner(text, actionLabel, onAction) {
    if (banner) banner.remove();
    banner = document.createElement("aside");
    banner.className = "pwa-install-card";
    banner.setAttribute("role", "region");
    banner.setAttribute("aria-label", "نصب اپ کی‌داره");
    banner.innerHTML = `
      <span class="pwa-install-icon" aria-hidden="true">ک</span>
      <div class="pwa-install-copy"><strong>کی‌داره رو نصب کن، سریع‌تر باز می‌شه</strong><p>${text}</p></div>
      <button class="button button-primary pwa-install-action" type="button"></button>
      <button class="pwa-install-close button button-ghost" type="button">بعداً</button>`;
    banner.querySelector(".pwa-install-action").textContent = actionLabel;
    banner.querySelector(".pwa-install-action").addEventListener("click", onAction);
    banner.querySelector(".pwa-install-close").addEventListener("click", () => {
      track("pwa_install_dismissed");
      dismiss();
    });
    document.body.appendChild(banner);
    return banner;
  }

  async function nativeInstall() {
    if (!installPrompt) return;
    const promptEvent = installPrompt;
    installPrompt = null;
    try {
      await promptEvent.prompt();
      const choice = await promptEvent.userChoice;
      track("pwa_install_choice", { outcome: choice?.outcome || "unknown" });
    } catch {
      UI.toast("نصب الان ممکن نشد؛ بعداً دوباره امتحان کن.", { kind: "error" });
    }
    if (banner) banner.hidden = true;
  }

  function showIosGuide() {
    let guide = document.querySelector("#pwaIosGuide");
    if (!guide) {
      guide = document.createElement("aside");
      guide.id = "pwaIosGuide";
      guide.className = "pwa-install-card";
      guide.setAttribute("role", "region");
      guide.setAttribute("aria-label", "راهنمای نصب در iOS");
      guide.innerHTML = `
        <span class="pwa-install-icon" aria-hidden="true">⬆</span>
        <div class="pwa-install-copy"><strong>نصب کی‌داره روی آیفون</strong>
          <p>دکمهٔ <span aria-hidden="true">⬆</span> «اشتراک‌گذاری» را بزن و «Add to Home Screen» را انتخاب کن.</p></div>
        <button class="pwa-install-close button button-ghost" type="button">بعداً</button>`;
      guide.querySelector("button").addEventListener("click", () => {
        track("pwa_ios_guide_dismissed");
        dismiss();
      });
      document.body.appendChild(guide);
    }
    banner = guide;
    guide.hidden = false;
  }

  function offerInstall() {
    if (engagementShown) return;
    const path = Rules.installPath({ hasNativePrompt: Boolean(installPrompt), userAgent: navigator.userAgent });
    if (path === "native") {
      engagementShown = true;
      createBanner("برای دسترسی سریع‌تر، کی‌داره را به صفحهٔ اصلی گوشی اضافه کن.", "نصب", nativeInstall);
      track("pwa_install_offered", { path });
    } else if (path === "ios-guide") {
      engagementShown = true;
      showIosGuide();
      track("pwa_install_offered", { path });
    }
  }

  // محرک‌ها: ۱۵ ثانیه ماندن، اسکرول ۵۰٪، یا کلیک روی صفحهٔ محصول
  function maybeOfferOnEngagement(extra = {}) {
    if (!Rules.canOfferInstall({ isStandalone: isStandalone(), dismissedAt: readDismissedAt(), now: Date.now() })) return;
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const scrollRatio = scrollable > 0 ? window.scrollY / scrollable : 1;
    if (Rules.isEngagementTriggered({ residenceMs: Date.now() - pageLoadedAt, scrollRatio, ...extra })) {
      offerInstall();
    }
  }

  function wireEngagement() {
    const timer = window.setInterval(() => {
      maybeOfferOnEngagement();
      if (engagementShown) window.clearInterval(timer);
    }, 1000);
    window.addEventListener("scroll", () => maybeOfferOnEngagement(), { passive: true });
    document.addEventListener("click", event => {
      const link = event.target.closest?.('a[href^="/product/"]');
      if (link) maybeOfferOnEngagement({ clickedProduct: true });
    });
  }

  // ---------- Service Worker + اعلان نسخهٔ جدید ----------
  function announceUpdate(registration) {
    UI.toast("نسخه‌ی جدید آماده است، بروزرسانی کنم؟", {
      kind: "info",
      duration: 12000,
      action: {
        label: "بروزرسانی",
        onClick: () => registration.waiting?.postMessage({ type: "SKIP_WAITING" }),
      },
    });
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    if (!(location.protocol === "https:" || location.hostname === "localhost")) return;
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" })
        .then(registration => {
          if (registration.waiting && navigator.serviceWorker.controller) announceUpdate(registration);
          registration.addEventListener("updatefound", () => {
            const worker = registration.installing;
            worker?.addEventListener("statechange", () => {
              if (worker.state === "installed" && navigator.serviceWorker.controller) announceUpdate(registration);
            });
          });
          return registration.update();
        })
        .catch(() => { /* سایت بدون Service Worker هم کار می‌کند */ });
    });
    let reloading = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (reloading) return;
      reloading = true;
      try { localStorage.setItem(UPDATED_KEY, "1"); } catch { /* ignore */ }
      window.location.reload();
    });
  }

  function announceFreshInstallIfAny() {
    try {
      if (localStorage.getItem(UPDATED_KEY) === "1") {
        localStorage.removeItem(UPDATED_KEY);
        UI.toast("نسخه‌ی جدید نصب شد 🎉", { kind: "success" });
      }
    } catch { /* ignore */ }
  }

  // ---------- Install events ----------
  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault(); // بنر پیش‌فرض مرورگر را پنهان کن؛ بنر خودمان را نشان می‌دهیم
    installPrompt = event;
    track("pwa_install_prompt_captured");
  });

  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    if (banner) banner.hidden = true;
    track("pwa_installed");
    UI.toast("کی‌داره نصب شد. حالا از صفحهٔ اصلی گوشی باز کن! 🎉", { kind: "success" });
  });

  document.querySelector("#installAppButton")?.addEventListener("click", () => {
    if (installPrompt) nativeInstall();
    else showIosGuide();
  });

  document.querySelectorAll(".mobile-nav-item").forEach(link => {
    const path = window.location.pathname.replace(/\/$/, "") || "/";
    const target = (link.getAttribute("href") || "").split("#")[0].replace(/\/$/, "") || "/";
    if (target === path) link.setAttribute("aria-current", "page");
  });

  announceFreshInstallIfAny();
  wireEngagement();
  registerServiceWorker();
})();
