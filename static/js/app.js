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
            ${item.image_path ? '<img class="listing-photo" src="' + escapeHTML(item.image_path) + '" alt="' + escapeHTML(item.title) + '" loading="lazy">' : '<span class="listing-emoji" aria-hidden="true">' + escapeHTML(item.emoji) + '</span>'}
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
    const detailButton = event.target.closest("[data-detail]");
    if (detailButton) {
      openListingDetails(detailButton.dataset.detail);
    }
  });


  const listingDialog = document.querySelector("#listingDialog");
  const dialogEmoji = document.querySelector("#dialogEmoji");
  const dialogMeta = document.querySelector("#dialogMeta");
  const dialogTitle = document.querySelector("#dialogTitle");
  const dialogPrice = document.querySelector("#dialogPrice");
  const dialogDescription = document.querySelector("#dialogDescription");
  const sellerContact = document.querySelector("#sellerContact");
  const sellerCallLink = document.querySelector("#sellerCallLink");

  async function openListingDetails(id) {
    try {
      const response = await fetch(`/api/listings/${encodeURIComponent(id)}`, {
        headers: { Accept: "application/json" }
      });
      const data = await response.json();
      if (!response.ok || !data.item) throw new Error("آگهی پیدا نشد.");
      const item = data.item;
      dialogEmoji.textContent = item.emoji || "🛍️";
      dialogEmoji.style.backgroundImage = item.image_path ? 'url("' + item.image_path + '")' : "";
      dialogEmoji.classList.toggle("has-photo", Boolean(item.image_path));
      dialogMeta.textContent = `${item.city} · ${categoryName(item.category)}`;
      dialogTitle.textContent = item.title;
      dialogPrice.textContent = Number(item.price) > 0
        ? `${numberFormat.format(item.price)} تومان`
        : "قیمت توافقی";
      dialogDescription.textContent = item.description || "توضیحی برای این آگهی ثبت نشده است.";
      if (item.seller_phone) {
        sellerCallLink.href = "tel:" + item.seller_phone;
        sellerCallLink.textContent = "تماس با فروشنده · " + item.seller_phone;
        sellerContact.hidden = false;
      } else {
        sellerCallLink.removeAttribute("href");
        sellerContact.hidden = true;
      }
      if (typeof listingDialog.showModal === "function") listingDialog.showModal();
      else showToast("برای مشاهده جزئیات، مرورگر را به‌روز کنید.");
    } catch (error) {
      showToast(error.message || "دریافت جزئیات آگهی ناموفق بود.");
    }
  }

  function closeListingDetails() {
    if (listingDialog.open) listingDialog.close();
  }

  document.querySelector("#closeListingDialog").addEventListener("click", closeListingDetails);
  document.querySelector("#dialogDone").addEventListener("click", closeListingDetails);
  listingDialog.addEventListener("click", (event) => {
    if (event.target === listingDialog) closeListingDetails();
  });

  const listingSubmitForm = document.querySelector("#listingSubmitForm");
  document.querySelector("#openListingForm").addEventListener("click", () => {
    listingSubmitForm.hidden = !listingSubmitForm.hidden;
    if (!listingSubmitForm.hidden) listingSubmitForm.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  const imageInput = listingSubmitForm.querySelector('input[name="image"]');
  const imagePreviewWrap = document.querySelector("#imagePreviewWrap");
  const imagePreview = document.querySelector("#imagePreview");
  let previewObjectUrl = "";

  function clearImagePreview() {
    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = "";
    imagePreview.removeAttribute("src");
    imagePreviewWrap.hidden = true;
    imageInput.value = "";
  }

  imageInput.addEventListener("change", () => {
    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = "";
    const file = imageInput.files && imageInput.files[0];
    if (!file) { imagePreviewWrap.hidden = true; return; }
    const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!allowedTypes.includes(file.type) || file.size > 4 * 1024 * 1024) {
      clearImagePreview();
      showToast("عکس باید JPG، PNG یا WebP و حداکثر ۴ مگابایت باشد.");
      return;
    }
    previewObjectUrl = URL.createObjectURL(file);
    imagePreview.src = previewObjectUrl;
    imagePreviewWrap.hidden = false;
  });

  document.querySelector("#removeImagePreview").addEventListener("click", clearImagePreview);

  listingSubmitForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(listingSubmitForm);
    formData.set("title", String(formData.get("title") || "").trim());
    formData.set("category", String(formData.get("category") || ""));
    formData.set("city", String(formData.get("city") || "").trim());
    formData.set("description", String(formData.get("description") || "").trim());
    const submitButton = listingSubmitForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.textContent = "در حال ثبت…";
    try {
      const response = await fetch("/api/listings", {
        method: "POST",
        headers: { Accept: "application/json" },
        body: formData
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "اطلاعات آگهی را بررسی کنید.");
      listingSubmitForm.reset();
      clearImagePreview();
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
