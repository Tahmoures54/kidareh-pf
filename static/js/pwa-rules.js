/* کی‌داره — منطق خالص نمایش بنر نصب (بدون DOM؛ قابل تست با Node) */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.KidarehPwaRules = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000;
  const RESIDENCE_TRIGGER_MS = 15 * 1000;
  const SCROLL_TRIGGER_RATIO = 0.5;

  // قانون اصلی: فقط اگر اپ نصب/standalone نیست و کاربر اخیراً dismiss نکرده.
  function canOfferInstall({ isStandalone, dismissedAt, now }) {
    if (isStandalone) return false;
    if (dismissedAt && now - dismissedAt < DISMISS_TTL_MS) return false;
    return true;
  }

  // هر یک از سه محرک کافی است: ۱۵ ثانیه ماندن، اسکرول ≥ ۵۰٪، یا کلیک روی صفحهٔ محصول.
  function isEngagementTriggered({ residenceMs, scrollRatio, clickedProduct }) {
    return residenceMs >= RESIDENCE_TRIGGER_MS ||
      scrollRatio >= SCROLL_TRIGGER_RATIO ||
      clickedProduct === true;
  }

  function isIosDevice(userAgent) {
    return /iphone|ipad|ipod/i.test(userAgent || "");
  }

  // iOS Safari هیچ beforeinstallprompt ندارد؛ راهنمای دستی لازم است.
  function installPath({ hasNativePrompt, userAgent }) {
    if (hasNativePrompt) return "native";
    if (isIosDevice(userAgent)) return "ios-guide";
    return "none";
  }

  return {
    DISMISS_TTL_MS,
    RESIDENCE_TRIGGER_MS,
    SCROLL_TRIGGER_RATIO,
    canOfferInstall,
    isEngagementTriggered,
    isIosDevice,
    installPath,
  };
});
