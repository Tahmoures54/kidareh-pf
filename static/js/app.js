(() => {
  const grid = document.querySelector("#listingGrid");
  const count = document.querySelector("#resultsCount");
  const empty = document.querySelector("#emptyState");
  const searchForm = document.querySelector("#searchForm");
  const searchInput = document.querySelector("#searchInput");
  const citySelect = document.querySelector("#citySelect");
  const toast = document.querySelector("#toast");
  const showAllButton = document.querySelector("#showAllButton");
  const clearFilters = document.querySelector("#clearFilters");
  const storeGrid = document.querySelector("#storeGrid");
  const storeSearchInput = document.querySelector("#storeSearchInput");

  if (!grid || !searchForm || !searchInput) return;

  let activeCategory = "all";
  let toastTimeout;
  let nearbyPosition = null;
  let listingsCursor = null;
  let listingsHasMore = false;
  let listingsLoadingMore = false;
  let listingsCache = [];
  let storeCursor = null;
  let storeHasMore = false;
  let storeCache = [];

  const numberFormat = new Intl.NumberFormat("fa-IR");
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

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("visible");
    window.clearTimeout(toastTimeout);
    toastTimeout = window.setTimeout(() => toast.classList.remove("visible"), 2800);
  }

  function categoryName(id) {
    const names = { home: "خانه و زندگی", digital: "دیجیتال", fashion: "پوشاک", vehicle: "خودرو", services: "خدمات", other: "سایر" };
    return names[id] || "آگهی";
  }

  function renderListings(items) {
    if (count) count.textContent = `${numberFormat.format(items.length)} کالا`;
    if (empty) empty.hidden = items.length !== 0;
    grid.hidden = items.length === 0;
    if (!items.length) {
      grid.innerHTML = "";
      return;
    }
    grid.innerHTML = items.map((item) => {
      const price = item.price > 0 ? `${numberFormat.format(item.price)} تومان` : "توافقی";
      return `
        <article class="listing-card">
          <div class="listing-image category-art-${escapeHTML(item.category)}">
            ${item.image_path ? '<img class="listing-photo" src="' + escapeHTML(item.image_path) + '" alt="' + escapeHTML(item.title) + '" loading="lazy">' : '<span class="listing-emoji" aria-hidden="true">' + escapeHTML(item.emoji || "🛍️") + '</span>'}
            ${item.featured ? '<span class="featured-label">پیشنهاد ویژه</span>' : ""}
            ${item.paid_tag ? '<span class="paid-listing-tag tag-' + escapeHTML(item.paid_tag.type) + '">' + escapeHTML(item.paid_tag.label) + '</span>' : ""}
          </div>
          <div class="listing-details">
            <div class="listing-meta"><span>${escapeHTML(item.city)}</span><span class="meta-dot"></span><span>${escapeHTML(categoryName(item.category))}</span>${item.distance_km != null ? `<span class="meta-dot"></span><span>${numberFormat.format(item.distance_km)} کیلومتر</span>` : ""}</div>
            <h3>${escapeHTML(item.title)}</h3>
            <p>${escapeHTML(item.description || "")}</p>
            <div class="listing-footer"><strong>${price}</strong><a class="listing-more" href="/product/${item.id}">جزئیات ←</a></div>
          </div>
        </article>`;
    }).join("");
  }

  function ensureLoadMoreButton() {
    let btn = document.querySelector("#loadMoreListings");
    if (!btn) {
      btn = document.createElement("button");
      btn.id = "loadMoreListings";
      btn.type = "button";
      btn.className = "button button-outline";
      btn.style.display = "none";
      btn.style.margin = "1rem auto";
      btn.textContent = "نمایش کالاهای بیشتر";
      grid.insertAdjacentElement("afterend", btn);
      btn.addEventListener("click", () => loadListings({ append: true }));
    }
    return btn;
  }

  async function loadListings(options = {}) {
    const append = Boolean(options.append);
    if (append && (listingsLoadingMore || !listingsHasMore)) return;
    const params = new URLSearchParams();
    const query = searchInput.value.trim();
    const city = citySelect ? citySelect.value : "";
    if (query) params.set("q", query);
    if (city) params.set("city", city);
    if (activeCategory !== "all") params.set("category", activeCategory);
    params.set("limit", "50");
    if (append && listingsCursor) params.set("before_id", String(listingsCursor));
    if (nearbyPosition) {
      params.set("lat", nearbyPosition.latitude);
      params.set("lon", nearbyPosition.longitude);
      params.set("radius_km", "25");
    }
    grid.hidden = false;
    if (empty) empty.hidden = true;
    const loadMoreBtn = ensureLoadMoreButton();
    if (!append) {
      listingsCursor = null;
      listingsHasMore = false;
      listingsCache = [];
      grid.innerHTML = '<div class="loading-card">داریم آگهی‌ها رو پیدا می‌کنیم…</div>';
      loadMoreBtn.style.display = "none";
    } else {
      listingsLoadingMore = true;
      loadMoreBtn.disabled = true;
      loadMoreBtn.textContent = "در حال بارگذاری…";
    }
    try {
      const response = await fetch(`/api/listings?${params.toString()}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();
      const items = data.items || [];
      listingsCache = append ? listingsCache.concat(items) : items;
      listingsHasMore = Boolean(data.has_more);
      listingsCursor = data.next_before_id || (items.length ? items[items.length - 1].id : null);
      renderListings(listingsCache);
      loadMoreBtn.style.display = listingsHasMore && !nearbyPosition ? "block" : "none";
      loadMoreBtn.disabled = false;
      loadMoreBtn.textContent = "نمایش کالاهای بیشتر";
    } catch (_error) {
      if (!append) {
        grid.innerHTML = '<div class="loading-card error-card">دریافت آگهی‌ها با مشکل روبه‌رو شد. صفحه را دوباره بارگذاری کن.</div>';
        if (count) count.textContent = "خطا در دریافت";
      }
      loadMoreBtn.disabled = false;
      loadMoreBtn.textContent = "تلاش دوباره برای کالاهای بیشتر";
    } finally {
      listingsLoadingMore = false;
    }
  }

  function renderStores(items) {
    const storesCount = document.querySelector("#storesCount");
    if (storesCount) storesCount.textContent = numberFormat.format(items.length) + " فروشگاه";
    if (!storeGrid) return;
    if (!items.length) {
      storeGrid.innerHTML = '<div class="loading-card">فروشگاهی با این مشخصات پیدا نشد.</div>';
      return;
    }
    storeGrid.innerHTML = items.map((store) =>
      '<a class="store-card" href="/store/' + store.id + '">' +
      '<span class="store-card-mark">⌂</span><span class="store-card-copy"><strong>' + escapeHTML(store.name) +
      (store.blue_tick_active ? ' <span class="store-paid-badge">✓ تیک آبی</span>' : '') + '</strong><small>' +
      escapeHTML(store.city) + ' · ' + numberFormat.format(store.product_count || 0) +
      ' کالا</small><span>' + escapeHTML(store.description || "برای دیدن کالاها وارد ویترین شو.") +
      '</span></span></a>'
    ).join("");
  }

  function ensureStoreLoadMore() {
    if (!storeGrid) return null;
    let btn = document.querySelector("#loadMoreStores");
    if (!btn) {
      btn = document.createElement("button");
      btn.id = "loadMoreStores";
      btn.type = "button";
      btn.className = "button button-outline";
      btn.style.display = "none";
      btn.style.margin = "1rem auto";
      btn.textContent = "نمایش فروشگاه‌های بیشتر";
      storeGrid.insertAdjacentElement("afterend", btn);
      btn.addEventListener("click", () => loadStores(storeSearchInput ? storeSearchInput.value : "", { append: true }));
    }
    return btn;
  }

  async function loadStores(query = "", options = {}) {
    if (!storeGrid) return;
    const append = Boolean(options.append);
    if (append && !storeHasMore) return;
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    params.set("limit", "50");
    if (append && storeCursor) params.set("before_id", String(storeCursor));
    const btn = ensureStoreLoadMore();
    if (!append) {
      storeCache = [];
      storeCursor = null;
      storeHasMore = false;
      storeGrid.innerHTML = '<div class="loading-card">ویترین‌ها در حال بارگذاری‌اند…</div>';
      if (btn) btn.style.display = "none";
    }
    try {
      const response = await fetch("/api/stores?" + params.toString(), { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok) throw new Error("بارگذاری فروشگاه‌ها ناموفق بود.");
      const items = data.items || [];
      storeCache = append ? storeCache.concat(items) : items;
      storeHasMore = Boolean(data.has_more);
      storeCursor = data.next_before_id || (items.length ? items[items.length - 1].id : null);
      renderStores(storeCache);
      if (btn) {
        btn.style.display = storeHasMore ? "block" : "none";
        btn.disabled = false;
        btn.textContent = "نمایش فروشگاه‌های بیشتر";
      }
    } catch (_error) {
      if (!append) storeGrid.innerHTML = '<div class="loading-card error-card">دریافت فروشگاه‌ها انجام نشد. دوباره تلاش کن.</div>';
    }
  }

  if (searchForm) {
    const nearbyButton = document.createElement("button");
    nearbyButton.type = "button";
    nearbyButton.className = "button button-outline";
    nearbyButton.textContent = "کالاهای نزدیک من";
    searchForm.insertAdjacentElement("afterend", nearbyButton);
    nearbyButton.addEventListener("click", () => {
      if (nearbyPosition) {
        nearbyPosition = null;
        nearbyButton.textContent = "کالاهای نزدیک من";
        loadListings();
        return;
      }
      if (!navigator.geolocation) {
        showToast("موقعیت‌یابی در این مرورگر پشتیبانی نمی‌شود.");
        return;
      }
      nearbyButton.disabled = true;
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          nearbyPosition = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
          nearbyButton.textContent = "نمایش همه شهرها";
          nearbyButton.disabled = false;
          loadListings();
        },
        () => {
          showToast("اجازه موقعیت داده نشد؛ شهر را انتخاب کنید.");
          nearbyButton.disabled = false;
        },
        { timeout: 8000, maximumAge: 300000 }
      );
    });
  }

  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadListings();
    document.querySelector("#listings")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  citySelect?.addEventListener("change", () => loadListings());

  document.querySelectorAll("[data-search]").forEach((button) => {
    button.addEventListener("click", () => {
      searchInput.value = button.dataset.search;
      loadListings();
    });
  });

  document.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.category;
      document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip.dataset.filter === activeCategory));
      loadListings();
    });
  });

  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.filter;
      document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip === button));
      loadListings();
    });
  });

  showAllButton?.addEventListener("click", () => {
    activeCategory = "all";
    if (searchInput) searchInput.value = "";
    if (citySelect) citySelect.value = "";
    nearbyPosition = null;
    document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip.dataset.filter === "all"));
    loadListings();
    loadStores();
  });

  clearFilters?.addEventListener("click", () => showAllButton?.click());

  let storeSearchTimeout;
  storeSearchInput?.addEventListener("input", () => {
    window.clearTimeout(storeSearchTimeout);
    storeSearchTimeout = window.setTimeout(() => loadStores(storeSearchInput.value), 280);
  });
  document.querySelector("#showAllStores")?.addEventListener("click", () => {
    if (storeSearchInput) storeSearchInput.value = "";
    loadStores();
  });

  loadListings();
  loadStores();
})();
