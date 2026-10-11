/* کی‌داره — تور راهنما (خریدار + فروشنده). وضعیت در localStorage ذخیره می‌شود. */
(() => {
  "use strict";

  const BUYER_KEY = "kidareh-onboarding-done-v1";
  const SELLER_KEY = "kidareh-seller-onboarding-done-v1";

  const BUYER_STEPS = [
    { selector: "#marketCityCombobox, #citySelect, .home-location-bar", title: "اول شهرت را انتخاب کن", text: "کالاهای نزدیک خودت را می‌بینی. هر وقت خواستی می‌توانی شهر را عوض کنی یا از «اطراف من» استفاده کنی." },
    { selector: "#listings, #listingGrid, .listings-section", title: "کالا را پیدا کن", text: "با جست‌وجو و دسته‌بندی سریع‌تر به کالای موردنظرت برس. نشان «≈ تقریبی» یعنی قیمت را قبل از مراجعه هماهنگ کن." },
    { selector: ".mobile-bottom-nav, .desktop-nav, .home-bottom-nav", title: "هماهنگی حضوری", text: "از همین‌جا به ویترین‌ها، گفت‌وگوها و ثبت آگهی برو. خرید حضوری، با آرامش!" }
  ];

  const SELLER_STEPS = [
    { selector: "#sellerStoreForm, .seller-hero, .seller-console", title: "۱. ویترینت را کامل کن", text: "نام فروشگاه، شهر، آدرس و ساعات کاری را وارد کن. هرچه شفاف‌تر باشی، مشتری راحت‌تر حضوری می‌آید." },
    { selector: "#sellerProductForm, #productForm, [data-seller-products], .seller-products", title: "۲. اولین کالا را اضافه کن", text: "عنوان روشن، عکس واقعی و قیمت به‌روز بگذار. پیش‌نمایش زنده پایین فرم را ببین تا ویترینت را همان‌طور که مشتری می‌بیند چک کنی." },
    { selector: "#sellerShareBox, .seller-share, [data-share-store], .seller-hero-actions", title: "۳. لینک را پخش کن", text: "لینک ویترین را در واتساپ و شبکه‌های اجتماعی بفرست. مشتری را به سمت مغازه بکش — منتظر عبور عابر نمان." }
  ];

  function isDone(key) {
    try { return localStorage.getItem(key) === "1"; } catch { return true; }
  }
  function markDone(key) {
    try { localStorage.setItem(key, "1"); } catch { /* private mode */ }
  }

  function runTour(steps, storageKey) {
    if (isDone(storageKey)) return;
    let index = 0;
    const card = document.createElement("div");
    card.className = "onboarding-tip";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-live", "polite");
    card.setAttribute("aria-label", "راهنمای شروع کی‌داره");
    document.body.append(card);

    function close() {
      markDone(storageKey);
      card.remove();
    }

    function render() {
      const step = steps[index];
      const target = document.querySelector(step.selector);
      card.replaceChildren();
      const counter = document.createElement("small");
      counter.textContent = `مرحلهٔ ${index + 1} از ${steps.length}`;
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
      next.textContent = index === steps.length - 1 ? "متوجه شدم" : "بعدی";
      next.addEventListener("click", () => {
        if (index === steps.length - 1) close();
        else { index += 1; render(); }
      });
      actions.append(skip, next);
      card.append(counter, title, text, actions);
      if (target) {
        target.scrollIntoView({ block: "center", behavior: "smooth" });
        target.classList.add("onboarding-highlight");
        window.setTimeout(() => target.classList.remove("onboarding-highlight"), 1800);
      }
      next.focus();
    }

    render();
  }

  function start() {
    const path = (window.location.pathname || "/").replace(/\/$/, "") || "/";
    if (path === "/seller" || path.startsWith("/seller/")) {
      runTour(SELLER_STEPS, SELLER_KEY);
    } else if (path === "/" || path === "/search" || path === "/stores") {
      runTour(BUYER_STEPS, BUYER_KEY);
    }
  }

  if (document.readyState === "complete") window.setTimeout(start, 800);
  else window.addEventListener("load", () => window.setTimeout(start, 800));
})();
