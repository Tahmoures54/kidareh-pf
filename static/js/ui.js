/* کی‌داره — ابزارهای مشترک UI: Toast و Feedback فوری */
(() => {
  "use strict";

  const TOAST_MS = 3200;
  let hideTimer = null;

  // toast(message, { kind: "success"|"error"|"info", action: { label, onClick } })
  function toast(message, options = {}) {
    const el = document.getElementById("pageToast");
    if (!el) return;
    const kind = options.kind || "info";
    el.dataset.kind = kind;
    el.replaceChildren();
    const text = document.createElement("span");
    text.textContent = message;
    el.append(text);
    if (options.action) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "toast-action";
      btn.textContent = options.action.label;
      btn.addEventListener("click", () => {
        options.action.onClick?.();
        el.classList.remove("visible");
      });
      el.append(btn);
    }
    el.classList.add("visible");
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => el.classList.remove("visible"), options.duration || TOAST_MS);
  }

  // withOptimistic: UI زودتر به‌روز می‌شود؛ اگر سرور خطا بدهد، برمی‌گردد.
  async function withOptimistic({ apply, revert, request, success, failure }) {
    apply();
    try {
      const result = await request();
      if (success) toast(success, { kind: "success" });
      return result;
    } catch {
      revert();
      toast(failure || "ارتباط برقرار نشد، دوباره امتحان می‌کنیم؟", { kind: "error" });
      return null;
    }
  }

  window.KidarehUI = Object.freeze({ toast, withOptimistic });
})();
