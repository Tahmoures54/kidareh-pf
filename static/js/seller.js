(() => {
  const page = window.KIDAREH_PAGE || {};
  if (page.type !== "seller") return;

  const tokenMeta = document.querySelector('meta[name="csrf-token"]');
  const toast = document.querySelector("#pageToast");
  const fmt = new Intl.NumberFormat("fa-IR");
  const escapeHTML = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&","<":"<",">":">",'"':""","'":"&#39;"}[c]));

  function notify(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("visible");
    window.setTimeout(() => toast.classList.remove("visible"), 2600);
  }

  async function api(url, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (options.method && options.method !== "GET") {
      headers["X-CSRF-Token"] = tokenMeta?.content || "";
    }
    const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || data.error || "درخواست انجام نشد.");
    return data;
  }

  async function loadSellerListings(storeId) {
    const target = document.querySelector("#pageListings");
    if (!target || !storeId) return;
    target.innerHTML = '<div class="loading-card">در حال دریافت کالاهای ویترین…</div>';
    try {
      const data = await api("/api/stores/" + storeId);
      const items = data.items || [];
      target.innerHTML = items.length
        ? items.map((item) => {
            const price = Number(item.price) > 0 ? fmt.format(item.price) + " تومان" : "قیمت توافقی";
            const art = item.image_path
              ? '<img src="' + escapeHTML(item.image_path) + '" alt="' + escapeHTML(item.title) + '" loading="lazy">'
              : "<span>" + escapeHTML(item.emoji || "🛍️") + "</span>";
            return (
              '<article class="page-listing-card"><a class="page-listing-art" href="/product/' +
              item.id +
              '">' +
              art +
              '</a><div class="page-listing-body"><h3>' +
              escapeHTML(item.title) +
              "</h3><p>" +
              escapeHTML(item.description || "") +
              '</p><div class="page-listing-footer"><strong>' +
              price +
              '</strong><button type="button" data-delete-listing="' +
              item.id +
              '" class="button button-outline">حذف</button></div></div></article>'
            );
          }).join("")
        : '<div class="empty-page-state">هنوز کالایی در ویترین ثبت نکرده‌ای.</div>';
      const count = document.querySelector("#pageResultsCount");
      if (count) count.textContent = fmt.format(items.length) + " کالا";
      const productMetric = document.querySelector("#sellerProductMetric");
      if (productMetric) productMetric.textContent = fmt.format(items.length) + " کالا";
    } catch (e) {
      target.innerHTML = '<div class="empty-page-state">' + escapeHTML(e.message) + "</div>";
    }
  }

  async function initSeller() {
    const status = document.querySelector("#sellerStatus");
    const createForm = document.querySelector("#storeCreateForm");
    const editForm = document.querySelector("#storeEditForm");
    const productForm = document.querySelector("#sellerProductForm");
    const productFeedback = document.querySelector("#sellerProductFeedback");
    let storeId = null;

    try {
      const me = await api("/api/auth/me");
      if (!me.user) {
        if (status)
          status.innerHTML =
            'برای مدیریت ویترین باید <a href="/login">وارد حساب</a> شوی یا <a href="/register">ثبت‌نام</a> کنی.';
        if (productForm) productForm.hidden = true;
        return;
      }
      if (me.csrf_token && tokenMeta) tokenMeta.content = me.csrf_token;

      const mine = await api("/api/my/store");
      const store = mine.item;
      const storeMetric = document.querySelector("#sellerStoreMetric");
      const nextMetric = document.querySelector("#sellerNextStepMetric");
      const welcomeTitle = document.querySelector("#sellerWelcomeTitle");
      if (!store) {
        if (storeMetric) storeMetric.textContent = "هنوز ساخته نشده";
        if (nextMetric) nextMetric.textContent = "ساخت ویترین";
        if (welcomeTitle) welcomeTitle.textContent = "سلام " + (me.user.name || "فروشگاه‌دار") + "؛ ویترینت را بساز";
        const productMetric = document.querySelector("#sellerProductMetric");
        if (productMetric) productMetric.textContent = "۰ کالا";
        if (status)
          status.innerHTML =
            "<strong>سلام " +
            escapeHTML(me.user.name) +
            "</strong><br>هنوز ویترین نساخته‌ای. فرم زیر را پر کن.";
        if (createForm) createForm.hidden = false;
        if (editForm) editForm.hidden = true;
        if (productForm) productForm.hidden = true;
      } else {
        storeId = store.id;
        if (storeMetric) storeMetric.textContent = "فعال";
        if (nextMetric) nextMetric.textContent = "ثبت کالا";
        if (welcomeTitle) welcomeTitle.textContent = "سلام " + (me.user.name || store.name || "فروشگاه‌دار") + "؛ " + store.name;
        if (status)
          status.innerHTML =
            "<strong>" +
            escapeHTML(store.name) +
            "</strong><br>" +
            escapeHTML(store.city) +
            (store.description ? " · " + escapeHTML(store.description) : "");
        if (createForm) createForm.hidden = true;
        if (editForm) {
          editForm.hidden = false;
          editForm.name.value = store.name || "";
          editForm.city.value = store.city || "";
          editForm.description.value = store.description || "";
          if (editForm.category) {
          const existingCategory = store.category || "";
          if (existingCategory && !Array.from(editForm.category.options).some((option) => option.value === existingCategory)) {
            const legacyOption = document.createElement("option");
            legacyOption.value = existingCategory;
            legacyOption.textContent = existingCategory + " (صنف قبلی)";
            editForm.category.appendChild(legacyOption);
          }
          editForm.category.value = existingCategory;
        }
          if (editForm.address) editForm.address.value = store.address || "";
          if (editForm.latitude) editForm.latitude.value = store.latitude ?? "";
          if (editForm.longitude) editForm.longitude.value = store.longitude ?? "";
        }
        if (productForm) productForm.hidden = false;

        const shareBtn = document.querySelector("#shareMyStore");
        const copyBtn = document.querySelector("#copyStorePromo");
        if (shareBtn) {
          shareBtn.hidden = false;
          shareBtn.dataset.shareUrl = "/store/" + store.id;
          shareBtn.dataset.shareTitle = "ویترین " + store.name;
        }
        if (copyBtn) {
          copyBtn.hidden = false;
          const promo =
            "ویترین «" +
            store.name +
            "» در کی‌داره:\n" +
            location.origin +
            "/store/" +
            store.id +
            "\nکالاها را ببین و برای خرید حضوری هماهنگ کن.";
          copyBtn.addEventListener("click", async () => {
            try {
              await navigator.clipboard.writeText(promo);
              notify("متن معرفی کپی شد.");
            } catch {
              notify("کپی پشتیبانی نشد.");
            }
          });
        }
        await loadSellerListings(storeId);
      }

      createForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          await api("/api/stores", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: createForm.name.value.trim(),
              city: createForm.city.value.trim(),
              description: createForm.description.value.trim(),
              category: createForm.category?.value || "",
            }),
          });
          notify("ویترین ساخته شد.");
          location.reload();
        } catch (err) {
          notify(err.message);
        }
      });

      editForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!storeId) return;
        try {
          await api("/api/stores/" + storeId, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: editForm.name.value.trim(),
              city: editForm.city.value.trim(),
              description: editForm.description.value.trim(),
              category: editForm.category?.value || "",
              address: editForm.address?.value.trim() || "",
              latitude: editForm.latitude?.value || "",
              longitude: editForm.longitude?.value || "",
            }),
          });
          notify("اطلاعات ویترین ذخیره شد.");
          location.reload();
        } catch (err) {
          notify(err.message);
        }
      });

      productForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!storeId) {
          notify("ابتدا ویترین بساز.");
          return;
        }
        const btn = productForm.querySelector('button[type="submit"]');
        const old = btn?.textContent;
        if (btn) {
          btn.disabled = true;
          btn.textContent = "در حال ثبت…";
        }
        if (productFeedback) productFeedback.textContent = "";
        try {
          const fd = new FormData(productForm);
          const response = await fetch("/api/listings", {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "X-CSRF-Token": tokenMeta?.content || "",
              Accept: "application/json",
            },
            body: fd,
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(data.message || data.error || "ثبت کالا انجام نشد.");
          notify("کالا ثبت شد.");
          productForm.reset();
          if (productFeedback) {
            productFeedback.textContent = "کالا با موفقیت به ویترین اضافه شد.";
            productFeedback.style.color = "#0E7490";
          }
          await loadSellerListings(storeId);
        } catch (err) {
          if (productFeedback) {
            productFeedback.textContent = err.message;
            productFeedback.style.color = "#B91C1C";
          }
          notify(err.message);
        } finally {
          if (btn) {
            btn.disabled = false;
            btn.textContent = old;
          }
        }
      });

      document.addEventListener("click", async (e) => {
        const del = e.target.closest("[data-delete-listing]");
        if (!del) return;
        if (!confirm("این کالا حذف شود؟")) return;
        try {
          await api("/api/listings/" + del.dataset.deleteListing, { method: "DELETE" });
          notify("کالا حذف شد.");
          await loadSellerListings(storeId);
        } catch (err) {
          notify(err.message);
        }
      });
    } catch (e) {
      if (status) status.textContent = e.message || "بارگذاری پنل فروشنده ناموفق بود.";
    }
  }

  initSeller();
})();
