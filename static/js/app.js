(() => {
  const grid = document.querySelector("#listingGrid");
  const count = document.querySelector("#resultsCount");
  const empty = document.querySelector("#emptyState");
  const searchForm = document.querySelector("#searchForm");
  const searchInput = document.querySelector("#searchInput");
  const citySelect = document.querySelector("#citySelect");
  const categorySelect = document.querySelector("#categorySelect");
  const activeMarketCity = document.querySelector("#activeMarketCity");
  const marketListingsTitle = document.querySelector("#marketListingsTitle");
  const changeMarketCityButton = document.querySelector("#changeMarketCityButton");
  const findMyLocationButton = document.querySelector("#findMyLocationButton");
  const nearbyListingsButton = document.querySelector("#nearbyListingsButton");
  const showAllButton = document.querySelector("#showAllButton");
  const clearFilters = document.querySelector("#clearFilters");
  const toast = document.querySelector("#toast");
  const storeGrid = document.querySelector("#storeGrid");
  const storesCount = document.querySelector("#storesCount");
  const storeSearchInput = document.querySelector("#storeSearchInput");
  const numberFormat = new Intl.NumberFormat("fa-IR");
  let currentFilter = "all";
  let userCoords = null;

  const categoryNames = {
    home: "خانه و زندگی",
    digital: "دیجیتال",
    fashion: "پوشاک",
    vehicle: "خودرو و حمل‌ونقل",
    services: "خدمات"
  };

  const escapeHTML = (value) => {
    const map = {
      "&": "&" + "amp;",
      "<": "&" + "lt;",
      ">": "&" + "gt;",
      '"': "&" + "quot;",
      "'": "&" + "#39;"
    };
    return String(value ?? "").replace(/[&<>"']/g, (char) => map[char]);
  };

  const categoryName = (id, label) => label || categoryNames[id] || id || "سایر";

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(() => toast.classList.remove("show"), 2800);
  }

  function ensureLoadMoreButton() {
    let btn = document.querySelector("#loadMoreListings");
    if (!btn && grid) {
      btn = document.createElement("button");
      btn.id = "loadMoreListings";
      btn.type = "button";
      btn.className = "button button-outline";
      btn.textContent = "نمایش بیشتر";
      btn.hidden = true;
      grid.parentElement?.appendChild(btn);
      btn.addEventListener("click", () => {
        if (btn.dataset.cursor) loadListings({ cursor: btn.dataset.cursor, append: true });
      });
    }
    return btn;
  }

  function renderListings(items, append) {
    if (!grid) return;
    if (!append) {
      if (!items.length) {
        grid.innerHTML = "";
        if (empty) empty.hidden = false;
        if (count) count.textContent = "۰ نتیجه";
        return;
      }
      if (empty) empty.hidden = true;
    }
    const html = items.map((item) => {
      return `
        <a class="listing-card" href="/product/${escapeHTML(item.id)}">
          <div class="listing-image category-art-${escapeHTML(item.category)}">
            ${item.image_path ? '<img class="listing-photo" src="' + escapeHTML(item.image_path) + '" alt="' + escapeHTML(item.title) + '" loading="lazy">' : '<span class="listing-emoji" aria-hidden="true">' + escapeHTML(item.emoji || "🛍️") + '</span>'}
            ${item.paid_tag ? '<span class="paid-listing-tag tag-' + escapeHTML(item.paid_tag.type) + '">' + escapeHTML(item.paid_tag.label) + '</span>' : ""}
          </div>
          <div class="listing-body">
            <div class="listing-meta"><span>${escapeHTML(item.city)}</span><span class="meta-dot"></span><span>${escapeHTML(categoryName(item.category, item.category_name))}</span>${item.distance_km != null ? `<span class="meta-dot"></span><span>${numberFormat.format(item.distance_km)} کیلومتر</span>` : ""}</div>
            <h3>${escapeHTML(item.title)}</h3>
            <p>${escapeHTML(item.description || "")}</p>
            <div class="listing-footer"><strong>${item.price ? numberFormat.format(item.price) + " تومان" : "توافقی"}</strong></div>
          </div>
        </a>`;
    }).join("");
    if (append) grid.insertAdjacentHTML("beforeend", html);
    else grid.innerHTML = html;
  }

  async function loadListings(opts = {}) {
    const params = new URLSearchParams();
    const q = (searchInput?.value || "").trim();
    const city = citySelect?.value.trim() || "تهران";
    if (q) params.set("q", q);
    if (city && !userCoords) params.set("city", city);
    if (currentFilter && currentFilter !== "all") params.set("category", currentFilter);
    if (userCoords) {
      params.set("lat", String(userCoords.lat));
      params.set("lon", String(userCoords.lng));
      params.set("radius_km", "25");
    }
    if (opts.cursor) params.set("cursor", opts.cursor);
    try {
      const res = await fetch("/api/listings?" + params.toString());
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "خطا");
      const items = data.items || [];
      renderListings(items, Boolean(opts.append));
      if (count && data.count != null) count.textContent = numberFormat.format(data.count) + " نتیجه";
      else if (count && !opts.append) count.textContent = numberFormat.format(items.length) + " نتیجه";
      const moreBtn = ensureLoadMoreButton();
      if (moreBtn) {
        if (data.next_cursor) {
          moreBtn.dataset.cursor = data.next_cursor;
          moreBtn.hidden = false;
        } else {
          moreBtn.hidden = true;
          delete moreBtn.dataset.cursor;
        }
      }
    } catch (err) {
      if (grid && !opts.append) grid.innerHTML = '<div class="loading-card">بارگذاری آگهی‌ها ممکن نشد.</div>';
      showToast("بارگذاری آگهی‌ها ممکن نشد.");
    }
  }

  function renderStores(items) {
    if (!storeGrid) return;
    if (!items.length) {
      storeGrid.innerHTML = '<div class="loading-card">فروشگاهی پیدا نشد.</div>';
      if (storesCount) storesCount.textContent = "۰ فروشگاه";
      return;
    }
    if (storesCount) storesCount.textContent = numberFormat.format(items.length) + " فروشگاه";
    storeGrid.innerHTML = items.map((store) => {
      return '<a class="store-card" href="/store/' + escapeHTML(store.id) + '">' +
      '<span class="store-card-mark">⌂</span><span class="store-card-copy"><strong>' + escapeHTML(store.name) +
      '</strong><small>' +
      escapeHTML(store.city) + ' · ' + numberFormat.format(store.product_count || 0) +
      ' کالا</small><span>' + escapeHTML(store.description || "برای دیدن کالاها وارد ویترین شو.") +
      '</span></span></a>';
    }).join("");
  }

  async function loadStores() {
    if (!storeGrid) return;
    const params = new URLSearchParams();
    const q = (storeSearchInput?.value || "").trim();
    if (q) params.set("q", q);
    try {
      const res = await fetch("/api/stores?" + params.toString());
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "خطا");
      renderStores(data.items || []);
      if (storesCount && data.count != null) storesCount.textContent = numberFormat.format(data.count) + " فروشگاه";
    } catch (err) {
      storeGrid.innerHTML = '<div class="loading-card">بارگذاری فروشگاه‌ها ممکن نشد.</div>';
    }
  }

  function updateMarketCity() {
    const city = citySelect?.value.trim() || "تهران";
    if (activeMarketCity) activeMarketCity.textContent = city;
    if (marketListingsTitle) marketListingsTitle.textContent = "بازار " + city;
  }

  function saveMarketCity() {
    const city = citySelect?.value.trim() || "";
    try {
      if (city) localStorage.setItem("kidareh.marketCity", city);
      else localStorage.removeItem("kidareh.marketCity");
    } catch (_) { /* City selection remains usable when storage is unavailable. */ }
    updateMarketCity();
  }

  try {
    const savedCity = localStorage.getItem("kidareh.marketCity");
    if (citySelect && savedCity) citySelect.value = savedCity;
  } catch (_) { /* Private browsing or storage restrictions should not block browsing. */ }
  updateMarketCity();

  searchForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    userCoords = null;
    if (categorySelect) currentFilter = categorySelect.value || "all";
    saveMarketCity();
    loadListings();
  });
  citySelect?.addEventListener("input", updateMarketCity);
  citySelect?.addEventListener("change", () => {
    userCoords = null;
    saveMarketCity();
    loadListings();
  });
  categorySelect?.addEventListener("change", () => {
    currentFilter = categorySelect.value || "all";
    loadListings();
  });

  document.querySelectorAll("[data-search]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (searchInput) searchInput.value = btn.dataset.search || "";
      loadListings();
    });
  });

  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
      currentFilter = chip.dataset.filter || "all";
      loadListings();
    });
  });

  document.querySelectorAll("[data-category]").forEach((tile) => {
    tile.addEventListener("click", () => {
      const cat = tile.dataset.category;
      currentFilter = cat || "all";
      document.querySelectorAll(".category-tile").forEach((c) => c.classList.toggle("active", c === tile));
      document.querySelectorAll(".filter-chip").forEach((c) => {
        c.classList.toggle("selected", (c.dataset.filter || "") === currentFilter || (currentFilter === "all" && c.dataset.filter === "all"));
      });
      document.querySelector("#listings")?.scrollIntoView({ behavior: "smooth" });
      loadListings();
    });
  });

  showAllButton?.addEventListener("click", () => {
    if (searchInput) searchInput.value = "";
    currentFilter = "all";
    if (categorySelect) categorySelect.value = "all";
    userCoords = null;
    document.querySelectorAll(".category-tile").forEach((c) => c.classList.remove("active"));
    document.querySelectorAll(".filter-chip").forEach((c) => c.classList.toggle("selected", c.dataset.filter === "all"));
    loadListings();
  });

  clearFilters?.addEventListener("click", () => showAllButton?.click());

  // Location is requested only after an explicit user action; never on page load.
  function requestNearbyLocation(sourceButton) {
    if (!navigator.geolocation) {
      showToast("مرورگر شما از مکان‌یابی پشتیبانی نمی‌کند.");
      return;
    }
    const buttons = [findMyLocationButton, nearbyListingsButton].filter(Boolean);
    buttons.forEach((button) => { button.disabled = true; });
    if (sourceButton) sourceButton.textContent = "در حال دریافت موقعیت…";
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        userCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        buttons.forEach((button) => { button.disabled = false; });
        if (findMyLocationButton) findMyLocationButton.textContent = "موقعیت پیدا شد ✓";
        if (nearbyListingsButton) nearbyListingsButton.textContent = "کالاهای اطراف من ✓";
        showToast("موقعیت فقط برای جست‌وجوی اطراف استفاده شد؛ شهر بازار تغییر نکرد.");
        loadListings();
      },
      () => {
        buttons.forEach((button) => { button.disabled = false; });
        if (findMyLocationButton) findMyLocationButton.textContent = "یافتن موقعیت من";
        if (nearbyListingsButton) nearbyListingsButton.textContent = "پیدا کردن کالاهای اطراف من";
        showToast("موقعیت دریافت نشد؛ می‌توانید شهر را دستی انتخاب کنید.");
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
    );
  }
  findMyLocationButton?.addEventListener("click", () => requestNearbyLocation(findMyLocationButton));
  nearbyListingsButton?.addEventListener("click", () => requestNearbyLocation(nearbyListingsButton));

  storeSearchInput?.addEventListener("input", () => {
    window.clearTimeout(storeSearchInput._t);
    storeSearchInput._t = window.setTimeout(loadStores, 280);
  });
  document.querySelector("#showAllStores")?.addEventListener("click", () => {
    if (storeSearchInput) storeSearchInput.value = "";
    loadStores();
  });

  // Compact, accessible homepage message ticker.
  (function initMarketTicker() {
    const root = document.querySelector("#marketTicker");
    const message = document.querySelector("#marketTickerMessage");
    const link = document.querySelector("#marketTickerLink");
    if (!root || !message || !link) return;
    const items = [
      { text: "کالاهای شهر را ببین؛ قبل از مراجعه، انتخاب کن.", label: "دیدن کالاها", href: "#listings" },
      { text: "فروشگاه‌دار هستی؟ ویترینت را رایگان بساز و به مشتری‌های شهر معرفی کن.", label: "ساخت ویترین", href: "/seller" },
      { text: "دنبال کالای خاصی هستی؟ جست‌وجو و دسته‌بندی‌ها کمکت می‌کنند زودتر پیدایش کنی.", label: "جست‌وجو", href: "/search" },
      { text: "کی‌داره برای خرید حضوری است؛ کالاها را ببین و برای مراجعه آماده شو.", label: "کشف فروشگاه‌ها", href: "/stores" },
      { text: "شهر بازار را خودت انتخاب کن؛ مکان‌یابی فقط با درخواست خودت انجام می‌شود.", label: "انتخاب شهر", href: "#marketCityCombobox" }
    ];
    let index = 0;
    let timer = null;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    function show(next) {
      index = (next + items.length) % items.length;
      message.textContent = items[index].text;
      link.href = items[index].href;
      link.firstChild.textContent = items[index].label + " ";
    }
    function stop() {
      if (timer) window.clearInterval(timer);
      timer = null;
    }
    function start() {
      stop();
      if (!reduceMotion && !document.hidden) timer = window.setInterval(() => show(index + 1), 5000);
    }
    root.addEventListener("mouseenter", stop);
    root.addEventListener("mouseleave", start);
    root.addEventListener("focusin", stop);
    root.addEventListener("focusout", (event) => {
      if (!root.contains(event.relatedTarget)) start();
    });
    root.addEventListener("touchstart", stop, { passive: true });
    root.addEventListener("touchend", start, { passive: true });
    document.addEventListener("visibilitychange", () => document.hidden ? stop() : start());
    show(0);
    start();
  })();

  loadListings();
  loadStores();
})();
