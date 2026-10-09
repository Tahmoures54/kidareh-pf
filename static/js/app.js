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
  let activeCategory = "all";
  let toastTimeout;

  const numberFormat = new Intl.NumberFormat("fa-IR");
  const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add("visible");
    window.clearTimeout(toastTimeout);
    toastTimeout = window.setTimeout(() => toast.classList.remove("visible"), 2800);
  }

  function renderListings(items) {
    count.textContent = `${numberFormat.format(items.length)} آگهی`;
    empty.hidden = items.length !== 0;
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
            <span class="listing-emoji" aria-hidden="true">${escapeHTML(item.emoji)}</span>
            ${item.featured ? '<span class="featured-label">پیشنهاد ویژه</span>' : ""}
            <button class="favorite-button" type="button" aria-label="ذخیره آگهی" data-favorite="${item.id}">♡</button>
          </div>
          <div class="listing-details">
            <div class="listing-meta"><span>${escapeHTML(item.city)}</span><span class="meta-dot"></span><span>${escapeHTML(categoryName(item.category))}</span></div>
            <h3>${escapeHTML(item.title)}</h3>
            <p>${escapeHTML(item.description)}</p>
            <div class="listing-footer"><strong>${price}</strong><button class="listing-more" type="button" data-detail="${item.id}" aria-label="جزئیات آگهی">←</button></div>
          </div>
        </article>`;
    }).join("");
  }

  function categoryName(id) {
    const names = { home: "خانه و زندگی", digital: "دیجیتال", fashion: "پوشاک", vehicle: "خودرو", services: "خدمات", other: "سایر" };
    return names[id] || "آگهی";
  }

  async function loadListings() {
    const params = new URLSearchParams();
    const query = searchInput.value.trim();
    const city = citySelect.value;
    if (query) params.set("q", query);
    if (city) params.set("city", city);
    if (activeCategory !== "all") params.set("category", activeCategory);
    grid.hidden = false;
    empty.hidden = true;
    grid.innerHTML = '<div class="loading-card">داریم آگهی‌ها رو پیدا می‌کنیم…</div>';
    try {
      const response = await fetch(`/api/listings?${params.toString()}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();
      renderListings(data.items || []);
    } catch (_error) {
      grid.innerHTML = '<div class="loading-card error-card">دریافت آگهی‌ها با مشکل روبه‌رو شد. صفحه را دوباره بارگذاری کن.</div>';
      count.textContent = "خطا در دریافت";
    }
  }

  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadListings();
    document.querySelector("#listings").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  citySelect.addEventListener("change", loadListings);

  document.querySelectorAll("[data-search]").forEach((button) => {
    button.addEventListener("click", () => {
      searchInput.value = button.dataset.search;
      loadListings();
      document.querySelector("#listings").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  document.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.category;
      document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip.dataset.filter === activeCategory));
      loadListings();
      document.querySelector("#listings").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.filter;
      document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip === button));
      document.querySelectorAll("[data-category]").forEach((tile) => tile.classList.toggle("active", tile.dataset.category === activeCategory));
      loadListings();
    });
  });

  grid.addEventListener("click", (event) => {
    const favorite = event.target.closest("[data-favorite]");
    if (favorite) {
      favorite.classList.toggle("is-favorite");
      favorite.textContent = favorite.classList.contains("is-favorite") ? "♥" : "♡";
      showToast(favorite.classList.contains("is-favorite") ? "این آگهی در این نسخه به‌صورت موقت نشان شد." : "از فهرست نشان‌شده‌های موقت برداشته شد.");
      return;
    }
    if (event.target.closest("[data-detail]")) {
      showToast("نمایش جزئیات و ارتباط با آگهی‌دهنده در مرحله بعدی پیاده‌سازی می‌شود.");
    }
  });

  const listingSubmitForm = document.querySelector("#listingSubmitForm");
  document.querySelector("#openListingForm").addEventListener("click", () => {
    listingSubmitForm.hidden = !listingSubmitForm.hidden;
    if (!listingSubmitForm.hidden) listingSubmitForm.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  listingSubmitForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(listingSubmitForm);
    const payload = {
      title: String(formData.get("title") || "").trim(),
      category: String(formData.get("category") || ""),
      city: String(formData.get("city") || "").trim(),
      price: Number(formData.get("price")),
      description: String(formData.get("description") || "").trim()
    };
    const submitButton = listingSubmitForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.textContent = "در حال ثبت…";
    try {
      const response = await fetch("/api/listings", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "اطلاعات آگهی را بررسی کنید.");
      listingSubmitForm.reset();
      listingSubmitForm.hidden = true;
      searchInput.value = "";
      citySelect.value = "";
      activeCategory = "all";
      document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip.dataset.filter === "all"));
      await loadListings();
      showToast("آگهی آزمایشی ثبت شد و در فهرست نمایش داده می‌شود.");
      document.querySelector("#listings").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      showToast(error.message || "ثبت آگهی انجام نشد؛ دوباره تلاش کنید.");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "ثبت آگهی آزمایشی";
    }
  });

  document.querySelector("#loginButton").addEventListener("click", () => {
    showToast("ورود و ثبت‌نام هنوز فعال نشده است؛ این نسخه فعلاً نمایشی است.");
  });

  showAllButton.addEventListener("click", () => {
    searchInput.value = "";
    citySelect.value = "";
    activeCategory = "all";
    document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip.dataset.filter === "all"));
    document.querySelectorAll("[data-category]").forEach((tile) => tile.classList.remove("active"));
    loadListings();
  });

  clearFilters.addEventListener("click", () => showAllButton.click());

  loadListings();
})();
