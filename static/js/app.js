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
  let currentUser = null;
  let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

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
  const ownerActions = document.querySelector("#ownerActions");
  let activeListing = null;

  async function openListingDetails(id) {
    try {
      const response = await fetch(`/api/listings/${encodeURIComponent(id)}`, {
        headers: { Accept: "application/json" }
      });
      const data = await response.json();
      if (!response.ok || !data.item) throw new Error("آگهی پیدا نشد.");
      const item = data.item;
      activeListing = item;
      ownerActions.hidden = !item.can_edit;
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


  document.querySelector("#editOwnListing").addEventListener("click", async () => {
    if (!activeListing) return;
    const title = window.prompt("عنوان آگهی", activeListing.title);
    if (title === null) return;
    const priceText = window.prompt("قیمت به تومان (برای توافقی عدد ۰)", String(activeListing.price));
    if (priceText === null) return;
    const description = window.prompt("توضیحات", activeListing.description || "");
    if (description === null) return;
    const city = window.prompt("شهر", activeListing.city);
    if (city === null) return;
    try {
      const response = await fetch("/api/listings/" + encodeURIComponent(activeListing.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ title, price: Number(priceText), description, city })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "ویرایش آگهی انجام نشد.");
      listingDialog.close();
      await loadListings();
      showToast("آگهی به‌روزرسانی شد.");
    } catch (error) {
      showToast(error.message || "ویرایش آگهی انجام نشد.");
    }
  });

  document.querySelector("#deleteOwnListing").addEventListener("click", async () => {
    if (!activeListing || !window.confirm("این آگهی برای همیشه حذف شود؟")) return;
    try {
      const response = await fetch("/api/listings/" + encodeURIComponent(activeListing.id), {
        method: "DELETE",
        headers: { Accept: "application/json", "X-CSRF-Token": csrfToken }
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "حذف آگهی انجام نشد.");
      listingDialog.close();
      await loadListings();
      showToast("آگهی حذف شد.");
    } catch (error) {
      showToast(error.message || "حذف آگهی انجام نشد.");
    }
  });

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
        headers: { Accept: "application/json", "X-CSRF-Token": csrfToken },
        body: formData
      });
      const data = await response.json();
      if (response.status === 401) {
        authDialog.showModal();
        throw new Error(data.message || "برای ثبت آگهی وارد حساب شوید.");
      }
      if (!response.ok) throw new Error(data.message || "اطلاعات آگهی را بررسی کنید.");
      listingSubmitForm.reset();
      clearImagePreview();
      listingSubmitForm.hidden = true;
      searchInput.value = "";
      citySelect.value = "";
      activeCategory = "all";
      document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip.dataset.filter === "all"));
      await loadListings();
      showToast("آگهی ثبت شد و در فهرست نمایش داده می‌شود.");
      document.querySelector("#listings").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      showToast(error.message || "ثبت آگهی انجام نشد؛ دوباره تلاش کنید.");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "ثبت آگهی آزمایشی";
    }
  });

  const authDialog = document.querySelector("#authDialog");
  const authForm = document.querySelector("#authForm");
  const authNameWrap = document.querySelector("#authNameWrap");
  const authModeToggle = document.querySelector("#authModeToggle");
  const authSubmit = document.querySelector("#authSubmit");
  const logoutButton = document.querySelector("#logoutButton");
  let authMode = "signup";

  function setAuthMode(mode) {
    authMode = mode;
    authNameWrap.hidden = mode !== "signup";
    authForm.elements.name.required = mode === "signup";
    authSubmit.textContent = mode === "signup" ? "ساخت حساب" : "ورود";
    authModeToggle.textContent = mode === "signup" ? "قبلاً حساب ساخته‌ام؛ ورود" : "حساب ندارم؛ ثبت‌نام";
    document.querySelector("#authTitle").textContent = mode === "signup" ? "ساخت حساب کی‌داره" : "ورود به کی‌داره";
  }

  function updateAuthUI(user) {
    currentUser = user || null;
    document.querySelector("#loginButton").textContent = currentUser ? currentUser.name : "ورود / ثبت‌نام";
    logoutButton.hidden = !currentUser;
    document.querySelector("#openListingForm").textContent = currentUser ? "ثبت آگهی جدید ←" : "برای ثبت آگهی وارد شوید ←";
  }

  document.querySelector("#loginButton").addEventListener("click", () => {
    setAuthMode("signup");
    authDialog.showModal();
  });
  document.querySelector("#closeAuthDialog").addEventListener("click", () => authDialog.close());
  authDialog.addEventListener("click", (event) => {
    if (event.target === authDialog) authDialog.close();
  });
  authModeToggle.addEventListener("click", () => setAuthMode(authMode === "signup" ? "login" : "signup"));

  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      name: authForm.elements.name.value.trim(),
      phone: authForm.elements.phone.value.trim(),
      password: authForm.elements.password.value
    };
    authSubmit.disabled = true;
    try {
      const response = await fetch(authMode === "signup" ? "/api/auth/signup" : "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "ورود یا ثبت‌نام انجام نشد.");
      csrfToken = data.csrf_token || csrfToken;
      updateAuthUI(data.user);
      authDialog.close();
      authForm.reset();
      setAuthMode("signup");
      showToast("با موفقیت وارد حساب شدید.");
    } catch (error) {
      showToast(error.message || "ارتباط برقرار نشد.");
    } finally {
      authSubmit.disabled = false;
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      const response = await fetch("/api/auth/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken, Accept: "application/json" } });
      if (!response.ok) throw new Error("خروج انجام نشد.");
      updateAuthUI(null);
      csrfToken = "";
      authDialog.close();
      showToast("از حساب خارج شدید.");
    } catch (error) {
      showToast(error.message);
    }
  });

  async function restoreSession() {
    try {
      const response = await fetch("/api/auth/me", { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (data.csrf_token) csrfToken = data.csrf_token;
      updateAuthUI(data.user);
    } catch (_error) {
      updateAuthUI(null);
    }
  }
  setAuthMode("signup");
  restoreSession();

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
