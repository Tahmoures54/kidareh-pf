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
  let currentStore = null;
  let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  let storeSearchTimeout;
  const storeGrid = document.querySelector("#storeGrid");
  const storeSearchInput = document.querySelector("#storeSearchInput");
  const savedIds = new Set(JSON.parse(localStorage.getItem("kidareh-saved-products") || "[]").map(String));

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
    count.textContent = `${numberFormat.format(items.length)} کالا`;
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
            <button class="favorite-button ${savedIds.has(String(item.id)) ? "is-favorite" : ""}" type="button" aria-label="ذخیره کالا" aria-pressed="${savedIds.has(String(item.id))}" data-favorite="${item.id}">${savedIds.has(String(item.id)) ? "♥" : "♡"}</button>
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
      const id = String(favorite.dataset.favorite);
      if (savedIds.has(id)) savedIds.delete(id); else savedIds.add(id);
      localStorage.setItem("kidareh-saved-products", JSON.stringify([...savedIds]));
      favorite.classList.toggle("is-favorite", savedIds.has(id));
      favorite.setAttribute("aria-pressed", String(savedIds.has(id)));
      favorite.textContent = savedIds.has(id) ? "♥" : "♡";
      showToast(savedIds.has(id) ? "کالا در ذخیره‌های این دستگاه قرار گرفت." : "کالا از ذخیره‌ها برداشته شد.");
      return;
    }
    const detailButton = event.target.closest("[data-detail]");
    if (detailButton) {
      openListingDetails(detailButton.dataset.detail);
    }
  });



  function renderStores(items) {
    document.querySelector("#storesCount").textContent = numberFormat.format(items.length) + " فروشگاه";
    if (!items.length) {
      storeGrid.innerHTML = '<div class="loading-card">فروشگاهی با این مشخصات پیدا نشد.</div>';
      return;
    }
    storeGrid.innerHTML = items.map((store) =>
      '<div class="store-card-wrap"><button class="store-card" type="button" data-store-id="' + store.id + '">' +
      '<span class="store-card-mark">⌂</span><span class="store-card-copy"><strong>' + escapeHTML(store.name) +
      '</strong><small>' + escapeHTML(store.city) + ' · ' + numberFormat.format(store.product_count || 0) +
      ' کالا</small><span>' + escapeHTML(store.description || "برای دیدن کالاهای این فروشگاه وارد ویترین شو.") +
      '</span></span><span class="store-card-arrow">←</span></button><button class="share-button" type="button" data-share-url="/store/' + store.id + '" data-share-title="ویترین ' + escapeHTML(store.name) + '">↗ معرفی ویترین</button></div>'
    ).join("");
  }

  async function loadStores(query = "") {
    storeGrid.innerHTML = '<div class="loading-card">ویترین‌ها در حال بارگذاری‌اند…</div>';
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      const response = await fetch("/api/stores?" + params.toString(), { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok) throw new Error("بارگذاری فروشگاه‌ها ناموفق بود.");
      renderStores(data.items || []);
    } catch (_error) {
      storeGrid.innerHTML = '<div class="loading-card error-card">دریافت فروشگاه‌ها انجام نشد. دوباره تلاش کن.</div>';
    }
  }

  const storeDialog = document.querySelector("#storeDialog");
  let activeStoreId = null;
  async function openStoreDetails(id) {
    activeStoreId = Number(id);
    try {
      const response = await fetch("/api/stores/" + encodeURIComponent(id), { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok) throw new Error("ویترین فروشگاه باز نشد.");
      const store = data.store;
      document.querySelector("#storeDialogTitle").textContent = store.name;
      document.querySelector("#storeDialogMeta").textContent = store.city + " · " + numberFormat.format(store.product_count || 0) + " کالا";
      document.querySelector("#storeDialogDescription").textContent = store.description || "به ویترین این فروشگاه خوش آمدید.";
      const shareStore = document.querySelector("#shareStoreDialog");
      shareStore.dataset.shareUrl = "/store/" + store.id;
      shareStore.dataset.shareTitle = "ویترین " + store.name;
      document.querySelector("#storeFollowersCount").textContent = numberFormat.format(store.follower_count || 0) + " دنبال‌کننده";
      const followButton = document.querySelector("#followStoreButton");
      followButton.textContent = data.following ? "✓ دنبال می‌کنی" : "♡ دنبال‌کردن فروشگاه";
      followButton.classList.toggle("is-following", Boolean(data.following));
      const products = data.items || [];
      document.querySelector("#storeProductsGrid").innerHTML = products.length ? products.map((item) =>
        '<article class="store-product-card"><button class="store-product-open" type="button" data-detail="' + item.id + '">' +
        (item.image_path ? '<img src="' + escapeHTML(item.image_path) + '" alt="' + escapeHTML(item.title) + '" loading="lazy">' :
          '<span class="store-product-emoji">' + escapeHTML(item.emoji || "🛍️") + '</span>') +
        '<strong>' + escapeHTML(item.title) + '</strong><small>' +
        (item.price > 0 ? numberFormat.format(item.price) + " تومان" : "قیمت توافقی") + '</small></button><button class="share-button" type="button" data-share-url="/product/' + item.id + '" data-share-title="کالای ' + escapeHTML(item.title) + '">↗ اشتراک‌گذاری</button></article>'
      ).join("") : '<p class="store-empty">این ویترین هنوز کالایی ندارد.</p>';
      storeDialog.showModal();
    } catch (error) {
      showToast(error.message || "خطا در بازکردن ویترین.");
    }
  }

  async function shareContent(url, title) {
    const absolute = new URL(url, location.origin).href;
    const message = (title || "این صفحه") + " در کی‌داره";
    try {
      if (navigator.share) { await navigator.share({ title: title || "کی‌داره", text: message, url: absolute }); return; }
      const popup = window.open("https://wa.me/?text=" + encodeURIComponent(message + "\\n" + absolute), "_blank", "noopener,noreferrer");
      if (!popup) { try { await navigator.clipboard.writeText(absolute); showToast("پیوند کپی شد؛ آن را در شبکه اجتماعی دلخواه بفرست."); } catch { showToast("پیوند صفحه: " + absolute); } }
    } catch (error) { if (error.name !== "AbortError") showToast("اشتراک‌گذاری انجام نشد."); }
  }
  document.addEventListener("click", async (event) => {
    const share = event.target.closest("[data-share-url]");
    if (share) { event.preventDefault(); event.stopPropagation(); await shareContent(share.dataset.shareUrl, share.dataset.shareTitle || ""); }
  });
  storeGrid.addEventListener("click", (event) => {
    const card = event.target.closest("[data-store-id]");
    if (card) openStoreDetails(card.dataset.storeId);
  });
  storeSearchInput.addEventListener("input", () => {
    window.clearTimeout(storeSearchTimeout);
    storeSearchTimeout = window.setTimeout(() => loadStores(storeSearchInput.value), 280);
  });
  document.querySelector("#showAllStores").addEventListener("click", () => {
    storeSearchInput.value = "";
    loadStores();
  });
  document.querySelector("#followStoreButton").addEventListener("click", async () => {
    if (!activeStoreId) return;
    if (!currentUser) {
      storeDialog.close();
      setAuthStage("phone");
      authDialog.showModal();
      loadCaptcha();
      showToast("برای دنبال‌کردن فروشگاه یک حساب ساده بساز یا وارد شو.");
      return;
    }
    const button = document.querySelector("#followStoreButton");
    button.disabled = true;
    try {
      const response = await fetch("/api/stores/" + activeStoreId + "/follow", {
        method: "POST",
        headers: { Accept: "application/json", "X-CSRF-Token": csrfToken }
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "تغییر دنبال‌کردن انجام نشد.");
      button.textContent = data.following ? "✓ دنبال می‌کنی" : "♡ دنبال‌کردن فروشگاه";
      button.classList.toggle("is-following", data.following);
      document.querySelector("#storeFollowersCount").textContent = numberFormat.format(data.follower_count || 0) + " دنبال‌کننده";
      showToast(data.following ? "فروشگاه به دنبال‌شده‌ها اضافه شد." : "فروشگاه از دنبال‌شده‌ها برداشته شد.");
      loadStores(storeSearchInput.value);
    } catch (error) {
      showToast(error.message || "خطا در دنبال‌کردن فروشگاه.");
    } finally {
      button.disabled = false;
    }
  });
  document.querySelector("#storeProductsGrid").addEventListener("click", (event) => {
    const product = event.target.closest("[data-detail]");
    if (!product) return;
    const productId = product.dataset.detail;
    storeDialog.close();
    openListingDetails(productId);
  });
    document.querySelector("#closeStoreDialog").addEventListener("click", () => storeDialog.close());
  storeDialog.addEventListener("click", (event) => { if (event.target === storeDialog) storeDialog.close(); });

  const storeCreateDialog = document.querySelector("#storeCreateDialog");
  const storeCreateForm = document.querySelector("#storeCreateForm");
  document.querySelector("#openStoreForm").addEventListener("click", async () => {
    if (!currentUser) {
      setAuthStage("phone");
      authDialog.showModal();
      loadCaptcha();
      showToast("برای ساخت ویترین، ابتدا وارد حساب شو.");
      return;
    }
    try {
      if (currentUser.role !== "seller") {
        const upgradeResponse = await fetch("/api/auth/become-seller", {
          method: "POST",
          headers: { Accept: "application/json", "X-CSRF-Token": csrfToken }
        });
        const upgradeData = await upgradeResponse.json();
        if (!upgradeResponse.ok) throw new Error(upgradeData.message || "تبدیل حساب به فروشنده انجام نشد.");
        currentUser = upgradeData.user;
      }
      const response = await fetch("/api/my/store", { headers: { Accept: "application/json" } });
      const data = await response.json();
      currentStore = data.item || null;
      if (currentStore) {
        showToast("ویترین شما از قبل ساخته شده است؛ می‌توانید کالا اضافه کنید.");
        listingSubmitForm.hidden = false;
        listingSubmitForm.scrollIntoView({ behavior: "smooth", block: "center" });
      } else {
        storeCreateDialog.showModal();
      }
    } catch (_error) {
      showToast("وضعیت ویترین دریافت نشد؛ دوباره تلاش کن.");
    }
  });
  document.querySelector("#closeStoreCreateDialog").addEventListener("click", () => storeCreateDialog.close());
  storeCreateDialog.addEventListener("click", (event) => { if (event.target === storeCreateDialog) storeCreateDialog.close(); });
  storeCreateForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = storeCreateForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const payload = Object.fromEntries(new FormData(storeCreateForm).entries());
      const response = await fetch("/api/stores", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "ساخت ویترین انجام نشد.");
      currentStore = data.item;
      storeCreateDialog.close();
      storeCreateForm.reset();
      await loadStores();
      showToast("ویترین ساخته شد؛ حالا کالاهایت را اضافه کن.");
      listingSubmitForm.hidden = false;
      listingSubmitForm.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (error) {
      showToast(error.message || "ساخت ویترین انجام نشد.");
    } finally {
      submit.disabled = false;
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
  document.querySelector("#openListingForm").addEventListener("click", async () => {
    if (!currentUser) {
      setAuthStage("phone");
      authDialog.showModal();
      loadCaptcha();
      showToast("برای افزودن کالا به ویترین، ابتدا وارد حساب شو.");
      return;
    }
    try {
      const response = await fetch("/api/my/store", { headers: { Accept: "application/json" } });
      const data = await response.json();
      currentStore = data.item || null;
      if (!currentStore) {
        storeCreateDialog.showModal();
        showToast("اول ویترین فروشگاهت را بساز؛ بعد کالا اضافه کن.");
        return;
      }
      listingSubmitForm.hidden = !listingSubmitForm.hidden;
      if (!listingSubmitForm.hidden) listingSubmitForm.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (_error) {
      showToast("اطلاعات ویترین دریافت نشد؛ دوباره تلاش کن.");
    }
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
        setAuthStage("phone");
        authDialog.showModal();
        loadCaptcha();
        throw new Error(data.message || "برای افزودن کالا وارد حساب شوید.");
      }
      if (response.status === 409 && data.error === "store_required") {
        showToast(data.message);
        storeCreateDialog.showModal();
        throw new Error(data.message);
      }
      if (!response.ok) throw new Error(data.message || "اطلاعات کالا را بررسی کنید.");
      listingSubmitForm.reset();
      clearImagePreview();
      listingSubmitForm.hidden = true;
      searchInput.value = "";
      citySelect.value = "";
      activeCategory = "all";
      document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip.dataset.filter === "all"));
      await loadListings();
      showToast("کالا به ویترین شما اضافه شد.");
      document.querySelector("#listings").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      showToast(error.message || "ثبت آگهی انجام نشد؛ دوباره تلاش کنید.");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "افزودن کالا به ویترین";
    }
  });

  const authDialog = document.querySelector("#authDialog");
  const authForm = document.querySelector("#authForm");
  const logoutButton = document.querySelector("#logoutButton");
  const phoneStep = document.querySelector("#authPhoneStep");
  const codeStep = document.querySelector("#authCodeStep");
  const profileStep = document.querySelector("#authProfileStep");
  const sellerDetails = document.querySelector("#sellerDetails");
  let authStage = "phone";
  let pendingPhone = "";

  async function loadCaptcha() {
    const response = await fetch("/api/auth/challenge", { headers: { Accept: "application/json" } });
    const data = await response.json();
    document.querySelector("#captchaQuestion").textContent = data.question || "پرسش امنیتی در دسترس نیست";
  }
  function setAuthStage(stage) {
    authStage = stage;
    phoneStep.hidden = stage !== "phone";
    codeStep.hidden = stage !== "code";
    profileStep.hidden = stage !== "profile";
    document.querySelector("#authTitle").textContent =
      stage === "phone" ? "ورود یا ساخت حساب" : stage === "code" ? "تأیید شماره همراه" : "تکمیل اطلاعات حساب";
    authForm.elements.name.required = stage === "profile";
    for (const name of ["store_name", "store_city"]) {
      authForm.elements[name].required = stage === "profile" && authForm.elements.role.value === "seller";
    }
  }
  function updateAuthUI(user) {
    currentUser = user || null;
    document.querySelector("#loginButton").textContent = currentUser ? currentUser.name : "ورود / ثبت‌نام";
    logoutButton.hidden = !currentUser;
    document.querySelector("#openListingForm").textContent = currentUser ? "افزودن کالا به ویترین ←" : "برای ساخت ویترین وارد شوید ←";
  }
  document.querySelector("#loginButton").addEventListener("click", async () => {
    setAuthStage("phone");
    authForm.reset();
    sellerDetails.hidden = true;
    authDialog.showModal();
    await loadCaptcha();
  });
  document.querySelector("#closeAuthDialog").addEventListener("click", () => authDialog.close());
  authDialog.addEventListener("click", (event) => { if (event.target === authDialog) authDialog.close(); });
  document.querySelector("#backToPhoneButton").addEventListener("click", async () => {
    setAuthStage("phone");
    await loadCaptcha();
  });
  authForm.elements.role.addEventListener("change", () => {
    sellerDetails.hidden = authForm.elements.role.value !== "seller";
    for (const name of ["store_name", "store_city"]) authForm.elements[name].required = authStage === "profile" && authForm.elements.role.value === "seller";
  });
  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = authStage === "phone" ? document.querySelector("#requestOtpButton") :
      authStage === "code" ? document.querySelector("#verifyOtpButton") : document.querySelector("#completeProfileButton");
    submit.disabled = true;
    try {
      let url, payload;
      if (authStage === "phone") {
        url = "/api/auth/request-otp";
        payload = { phone: authForm.elements.phone.value.trim(), captcha_answer: authForm.elements.captcha.value.trim(), terms_accepted: true };
      } else if (authStage === "code") {
        url = "/api/auth/verify-otp";
        payload = { code: authForm.elements.otp.value.trim() };
      } else {
        url = "/api/auth/complete-profile";
        payload = {
          name: authForm.elements.name.value.trim(), role: authForm.elements.role.value,
          store_name: authForm.elements.store_name.value.trim(), store_category: authForm.elements.store_category.value.trim(),
          store_city: authForm.elements.store_city.value.trim(), contact_name: authForm.elements.contact_name.value.trim(),
          store_address: authForm.elements.store_address.value.trim(), store_hours: authForm.elements.store_hours.value.trim(),
          store_description: authForm.elements.store_description.value.trim(),
          in_person: authForm.elements.in_person.checked
        };
      }
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        if (authStage === "phone" && data.error === "captcha_failed") await loadCaptcha();
        throw new Error(data.message || "عملیات انجام نشد.");
      }
      if (authStage === "phone") {
        pendingPhone = authForm.elements.phone.value.trim();
        document.querySelector("#otpPhoneLabel").textContent = pendingPhone;
        setAuthStage("code");
        showToast("کد تأیید ارسال شد.");
      } else if (authStage === "code") {
        if (data.existing_user) {
          csrfToken = data.csrf_token || csrfToken;
          updateAuthUI(data.user);
          authDialog.close();
          authForm.reset();
          sellerDetails.hidden = true;
          showToast("با موفقیت وارد حساب شدید.");
        } else {
          pendingPhone = data.phone || pendingPhone;
          setAuthStage("profile");
          showToast("شماره همراه تأیید شد.");
        }
      } else {
        csrfToken = data.csrf_token || csrfToken;
        updateAuthUI(data.user);
        currentStore = data.store || currentStore;
        authDialog.close();
        authForm.reset();
        sellerDetails.hidden = true;
        setAuthStage("phone");
        showToast("حساب شما با موفقیت ساخته شد.");
      }
    } catch (error) {
      showToast(error.message || "ارتباط برقرار نشد.");
    } finally {
      submit.disabled = false;
    }
  });

  async function restoreSession() {
    try {
      const response = await fetch("/api/auth/me", { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (data.csrf_token) csrfToken = data.csrf_token;
      updateAuthUI(data.user);
      if (data.user && data.user.role === "seller") {
        const storeResponse = await fetch("/api/my/store", { headers: { Accept: "application/json" } });
        const storeData = await storeResponse.json();
        currentStore = storeData.item || null;
      }
    } catch (_error) {
      updateAuthUI(null);
    }
  }
  setAuthStage("phone");
  restoreSession();
  loadStores();

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
