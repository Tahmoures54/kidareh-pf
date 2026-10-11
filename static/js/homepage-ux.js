(() => {
  "use strict";
  function enhanceHero() {
    const title = document.querySelector("#homeIntroTitle");
    const eyebrow = document.querySelector(".home-intro-eyebrow");
    const copy = document.querySelector(".home-intro-copy > p");
    const actions = document.querySelector(".home-intro-actions");
    const points = document.querySelector(".home-intro-points");
    if (eyebrow) eyebrow.innerHTML = '<span aria-hidden="true">✦</span> ببین کی داره؟ حضوری بگیر';
    if (title) title.innerHTML = 'کالای شهرت را پیدا کن،<br><span>حضوری هماهنگ کن.</span>';
    if (copy) copy.textContent = 'بدون ساخت حساب، کالاها و ویترین‌های شهر را ببین، قیمت‌ها را مقایسه کن و برای خرید حضوری با فروشنده هماهنگ شو.';
    if (actions) {
      actions.innerHTML = '<a class="button button-primary home-cta-primary" href="#listings">کالاهای شهر را ببین <span aria-hidden="true">↓</span></a>' +
        '<a class="button home-intro-secondary" href="/seller">فروشگاهی؟ ویترین بساز</a>';
    }
    if (points) {
      points.innerHTML = '<li><span aria-hidden="true">✓</span> جست‌وجو بدون ثبت‌نام</li>' +
        '<li><span aria-hidden="true">✓</span> هماهنگی حضوری با فروشنده</li>' +
        '<li><span aria-hidden="true">✓</span> تمرکز روی بازار محلی</li>';
    }
  }
  function enhanceEmpty() {
    const empty = document.querySelector("#emptyState");
    if (!empty) return;
    if (!document.querySelector("#emptyStateTitle")) {
      empty.innerHTML = '<span aria-hidden="true">⌕</span>' +
        '<h3 id="emptyStateTitle">در این شهر هنوز کالایی نیست</h3>' +
        '<p id="emptyStateText">شهر دیگری را امتحان کن، فیلترها را بردار، یا از جست‌وجوی «اطراف من» استفاده کن.</p>' +
        '<div class="empty-state-actions">' +
        '<button class="button button-primary" id="clearFilters" type="button">نمایش همه کالاها</button>' +
        '<button class="button button-outline" id="emptyTryNearby" type="button">کالاهای اطراف من</button>' +
        '<a class="button button-outline" href="/stores">دیدن فروشگاه‌ها</a></div>' +
        '<p class="empty-state-hint">فروشگاهی؟ <a href="/seller">ویترینت را رایگان بساز</a> تا مشتری‌های شهر پیدایت کنند.</p>';
    }
  }
  function ensureNearbyBanner() {
    if (document.querySelector("#nearbyActiveBanner")) return;
    const banner = document.createElement("div");
    banner.className = "nearby-active-banner";
    banner.id = "nearbyActiveBanner";
    banner.setAttribute("role", "status");
    banner.setAttribute("aria-live", "polite");
    banner.innerHTML = '<span id="nearbyActiveText">در حال نمایش کالاهای اطراف موقعیت شما (شعاع ۲۵ کیلومتر)</span>' +
      '<button type="button" id="clearNearbyMode">بازگشت به شهر انتخاب‌شده</button>';
    const main = document.querySelector("#main-content");
    if (main) main.parentNode.insertBefore(banner, main);
  }
  function run() { enhanceHero(); enhanceEmpty(); ensureNearbyBanner(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
})();
