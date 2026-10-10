(() => {
  const grid = document.querySelector("#listingGrid");
  const count = document.querySelector("#resultsCount");
  const empty = document.querySelector("#emptyState");
  const searchForm = document.querySelector("#searchForm");
  const searchInput = document.querySelector("#searchInput");
  const citySelect = document.querySelector("#citySelect");
  const showAllButton = document.querySelector("#showAllButton");
  const clearFilters = document.querySelector("#clearFilters");
  const toast = document.querySelector("#toast");
  const storeGrid = document.querySelector("#storeGrid");
  const storesCount = document.querySelector("#storesCount");
  const storeSearchInput = document.querySelector("#storeSearchInput");
  const numberFormat = new Intl.NumberFormat("fa-IR");
  let currentFilter = "all";
  let userCoords = null;
  let listingsCursor = null;
  let storesCursor = null;

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

  const categoryName = (id) => categoryNames[id] || id || "سایر";

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(() => toast.classList.remove("show"), 2800);
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
    if (count && !append) count.textContent = numberFormat.format(items.length) + " نتیجه";
    const html = items.map((item) => {
      return `
        <a class="listing-card" href="/listing/${escapeHTML(item.id)}">
          <div class="listing-image category-art-${escapeHTML(item.category)}">
            ${item.image_path ? '<img class="listing-photo" src="' + escapeHTML(item.image_path) + '" alt="' + escapeHTML(item.title) + '" loading="lazy">' : '<span class="listing-emoji" aria-hidden="true">' + escapeHTML(item.emoji || "🛍️") + '</span>'}
            ${item.paid_tag ? '<span class="paid-listing-tag tag-' + escapeHTML(item.paid_tag.type) + '">' + escapeHTML(item.paid_tag.label) + '</span>' : ""}
          </div>
          <div class="listing-body">
            <div class="listing-meta"><span>${escapeHTML(item.city)}</span><span class="meta-dot"></span><span>${escapeHTML(categoryName(item.category))}</span>${item.distance_km != null ? `<span class="meta-dot"></span><span>${numberFormat.format(item.distance_km)} کیلومتر</span>` : ""}</div>
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
    const city = citySelect?.value || "";
    if (q) params.set("q", q);
    if (city) params.set("city", city);
    if (currentFilter && currentFilter !== "all") params.set("category", currentFilter);
    if (userCoords) {
      params.set("lat", String(userCoords.lat));
      params.set("lng", String(userCoords.lng));
      params.set("radius_km", "25");
    }
    if (opts.cursor) params.set("cursor", opts.cursor);
    try {
      const res = await fetch("/api/listings?" + params.toString());
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "خطا");
      const items = data.items || [];
      listingsCursor = data.next_cursor || null;
      renderListings(items, Boolean(opts.cursor));
      if (count && data.count != null) count.textContent = numberFormat.format(data.count) + " نتیجه";
      const moreBtn = document.querySelector("#loadMoreListings");
      if (moreBtn) moreBtn.hidden = !listingsCursor;
    } catch (err) {
      if (grid && !opts.cursor) grid.innerHTML = '<div class="loading-card">بارگذاری آگهی‌ها ممکن نشد.</div>';
      showToast("بارگذاری آگهی‌ها ممکن نشد.");
    }
  }

  function renderStores(items, append) {
    if (!storeGrid) return;
    if (!items.length && !append) {
      storeGrid.innerHTML = '<div class="loading-card">فروشگاهی پیدا نشد.</div>';
      if (storesCount) storesCount.textContent = "۰ فروشگاه";
      return;
    }
    if (storesCount && !append) storesCount.textContent = numberFormat.format(items.length) + " فروشگاه";
    const html = items.map((store) => {
      return '<a class="store-card" href="/store/' + escapeHTML(store.id) + '">' +
      '<span class="store-card-mark">⌂</span><span class="store-card-copy"><strong>' + escapeHTML(store.name) +
      '</strong><small>' +
      escapeHTML(store.city) + ' · ' + numberFormat.format(store.product_count || 0) +
      ' کالا</small><span>' + escapeHTML(store.description || "برای دیدن کالاها وارد ویترین شو.") +
      '</span></span></a>';
    }).join("");
    if (append) storeGrid.insertAdjacentHTML("beforeend", html);
    else storeGrid.innerHTML = html;
  }

  async function loadStores(opts = {}) {
    if (!storeGrid) return;
    const params = new URLSearchParams();
    const q = (storeSearchInput?.value || "").trim();
    if (q) params.set("q", q);
    if (opts.cursor) params.set("cursor", opts.cursor);
    try {
      const res = await fetch("/api/stores?" + params.toString());
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "خطا");
      const items = data.items || [];
      storesCursor = data.next_cursor || null;
      renderStores(items, Boolean(opts.cursor));
      if (storesCount && data.count != null) storesCount.textContent = numberFormat.format(data.count) + " فروشگاه";
      const moreBtn = document.querySelector("#loadMoreStores");
      if (moreBtn) moreBtn.hidden = !storesCursor;
    } catch (err) {
      if (!opts.cursor) storeGrid.innerHTML = '<div class="loading-card">بارگذاری فروشگاه‌ها ممکن نشد.</div>';
    }
  }

  searchForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    listingsCursor = null;
    loadListings();
  });

  document.querySelectorAll("[data-search]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (searchInput) searchInput.value = btn.dataset.search || "";
      listingsCursor = null;
      loadListings();
    });
  });

  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
      currentFilter = chip.dataset.filter || "all";
      listingsCursor = null;
      loadListings();
    });
  });

  document.querySelectorAll("[data-category]").forEach((tile) => {
    tile.addEventListener("click", () => {
      const cat = tile.dataset.category;
      currentFilter = cat || "all";
      document.querySelectorAll(".filter-chip").forEach((c) => {
        c.classList.toggle("selected", (c.dataset.filter || "") === currentFilter || (currentFilter === "all" && c.dataset.filter === "all"));
      });
      document.querySelector("#listings")?.scrollIntoView({ behavior: "smooth" });
      listingsCursor = null;
      loadListings();
    });
  });

  showAllButton?.addEventListener("click", () => {
    if (searchInput) searchInput.value = "";
    if (citySelect) citySelect.value = "";
    currentFilter = "all";
    document.querySelectorAll(".filter-chip").forEach((c) => c.classList.toggle("selected", c.dataset.filter === "all"));
    listingsCursor = null;
    loadListings();
  });

  clearFilters?.addEventListener("click", () => showAllButton?.click());

  document.querySelector("#loadMoreListings")?.addEventListener("click", () => {
    if (listingsCursor) loadListings({ cursor: listingsCursor });
  });
  document.querySelector("#loadMoreStores")?.addEventListener("click", () => {
    if (storesCursor) loadStores({ cursor: storesCursor });
  });

  // Nearby button
  if (searchForm && navigator.geolocation) {
    const nearbyButton = document.createElement("button");
    nearbyButton.type = "button";
    nearbyButton.className = "button button-outline nearby-btn";
    nearbyButton.textContent = "کالاهای نزدیک من";
    nearbyButton.addEventListener("click", () => {
      nearbyButton.disabled = true;
      nearbyButton.textContent = "در حال یافتن موقعیت…";
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          userCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          nearbyButton.textContent = "نزدیک من ✓";
          nearbyButton.disabled = false;
          listingsCursor = null;
          loadListings();
        },
        () => {
          nearbyButton.textContent = "کالاهای نزدیک من";
          nearbyButton.disabled = false;
          showToast("دسترسی به موقعیت ممکن نشد.");
        },
        { enableHighAccuracy: false, timeout: 10000 }
      );
    });
    searchForm.insertAdjacentElement("afterend", nearbyButton);
  }

  storeSearchInput?.addEventListener("input", () => {
    window.clearTimeout(storeSearchInput._t);
    storeSearchInput._t = window.setTimeout(() => {
      storesCursor = null;
      loadStores();
    }, 280);
  });
  document.querySelector("#showAllStores")?.addEventListener("click", () => {
    if (storeSearchInput) storeSearchInput.value = "";
    storesCursor = null;
    loadStores();
  });

  // Large promo banners — fast rotation for lively feel
  (function initPromoBanner() {
    const root = document.querySelector("#promoBanner");
    const slides = Array.from(document.querySelectorAll("#promoSlides .promo-banner-slide"));
    const dots = Array.from(document.querySelectorAll("#promoDots .promo-dot"));
    if (slides.length < 2) return;
    let index = 0;
    let timer = null;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const INTERVAL_MS = 2200;

    function goTo(next) {
      const prev = index;
      index = ((next % slides.length) + slides.length) % slides.length;
      slides.forEach((el, i) => {
        el.classList.toggle("active", i === index);
        el.classList.toggle("exit", i === prev && prev !== index);
      });
      dots.forEach((dot, i) => {
        const on = i === index;
        dot.classList.toggle("active", on);
        dot.setAttribute("aria-selected", on ? "true" : "false");
      });
    }
    function start() {
      if (reduceMotion) return;
      stop();
      timer = window.setInterval(() => goTo(index + 1), INTERVAL_MS);
    }
    function stop() {
      if (timer) window.clearInterval(timer);
      timer = null;
    }
    dots.forEach((dot) => {
      dot.addEventListener("click", () => {
        goTo(Number(dot.dataset.slide) || 0);
        start();
      });
    });
    document.querySelector("#promoPrev")?.addEventListener("click", () => {
      goTo(index - 1);
      start();
    });
    document.querySelector("#promoNext")?.addEventListener("click", () => {
      goTo(index + 1);
      start();
    });
    root?.addEventListener("mouseenter", stop);
    root?.addEventListener("mouseleave", start);
    root?.addEventListener("focusin", stop);
    root?.addEventListener("focusout", start);
    start();
  })();

  loadListings();
  loadStores();
})();
