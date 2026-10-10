/* کی‌داره — تور ۳ مرحله‌ای اولین ورود (بدون وابستگی). وضعیت در localStorage ذخیره می‌شود. */
(() => {
  "use strict";

  const STORAGE_KEY = "kidareh-onboarding-done-v1";
  const STEPS = [
    { selector: "#marketCityCombobox", title: "اول شهرت را انتخاب کن", text: "کالاهای نزدیک خودت را می‌بینی. هر وقت خواستی می‌توانی شهر را عوض کنی." },
    { selector: "#listings, #listingGrid", title: "کالا را پیدا کن", text: "با جست‌وجو و دسته‌بندی، سریع‌تر به کالای موردنظرت برسی و آن را ذخیره کنی." },
    { selector: ".mobile-bottom-nav, .desktop-nav", title: "هماهنگی حضوری", text: "از همین‌جا به ویترین‌ها، گفت‌وگوها و ثبت آگهی برو. خرید حضوری، با آرامش!" }
  ];

  function isDone() {
    try { return localStorage.getItem(STORAGE_KEY) === "1"; } catch { return true; }
  }
  function markDone() {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch { /* private mode */ }
  }

  function start() {
    if (isDone()) return;
    let index = 0;
    const card = document.createElement("div");
    card.className = "onboarding-tip";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-live", "polite");
    card.setAttribute("aria-label", "راهنمای شروع کی‌داره");
    document.body.append(card);

    function close() {
      markDone();
      card.remove();
    }

    function render() {
      const step = STEPS[index];
      const target = document.querySelector(step.selector);
      card.replaceChildren();
      const counter = document.createElement("small");
      counter.textContent = `مرحلهٔ ${index + 1} از ${STEPS.length}`;
      const title = document.createElement("strong");
      title.textContent = step.title;
      const text = document.createElement("p");
      text.textContent = step.text;
      const actions = document.createElement("div");
      actions.className = "onboarding-actions";
      const skip = document.createElement("button");
      skip.type = "button";
      skip.className = "button button-ghost";
      skip.textContent = "رد کردن";
      skip.addEventListener("click", close);
      const next = document.createElement("button");
      next.type = "button";
      next.className = "button button-primary";
      next.textContent = index === STEPS.length - 1 ? "متوجه شدم" : "بعدی";
      next.addEventListener("click", () => {
        if (index === STEPS.length - 1) close();
        else { index += 1; render(); }
      });
      actions.append(skip, next);
      card.append(counter, title, text, actions);
      if (target) target.scrollIntoView({ block: "center", behavior: "smooth" });
      next.focus();
    }

    render();
  }

  // کمی بعد از بارگذاری، تا صفحه پایدار شود
  if (document.readyState === "complete") window.setTimeout(start, 800);
  else window.addEventListener("load", () => window.setTimeout(start, 800));
})();
