(() => {
  const page = window.KIDAREH_PAGE || {};
  if (page.type !== "seller") return;

  const tokenMeta = document.querySelector('meta[name="csrf-token"]');
  const toast = document.querySelector("#pageToast");
  const fmt = new Intl.NumberFormat("fa-IR");
  const escapeHTML = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

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
              '</p><div class="seller-stock-status">' +
              (item.availability_status === "in_stock" ? "موجود است" : item.availability_status === "out_of_stock" ? "فعلاً ناموجود" : "موجودی را از فروشنده بپرسید") +
              (item.price_updated_at ? " · آخرین به‌روزرسانی قیمت: " + escapeHTML(new Date(item.price_updated_at).toLocaleDateString("fa-IR")) : "") +
              '</div><div class="page-listing-footer"><strong>' +
              price +
              '</strong><button type="button" data-delete-listing="' +
              item.id +
              '" class="button button-outline">حذف</button></div></div></article>'
            );
          }).join("")
        : '<div class="empty-page-state"><span aria-hidden="true">＋</span><h3>ویترین هنوز خالی است</h3><p>اولین کالا را با عنوان روشن، عکس واقعی و قیمت به‌روز اضافه کن تا مشتری‌های شهر پیدایت کنند.</p></div>';
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

      if (me.user.role !== "seller") {
        if (status) {
          status.innerHTML =
            "حساب فعلی شما خریدار است. برای ساخت ویترین و ثبت کالا، حساب را به فروشنده تبدیل کنید." +
            ' <button type="button" class="button button-primary" id="becomeSellerButton">تبدیل حساب به فروشنده</button>';
        }
        if (createForm) createForm.hidden = true;
        if (editForm) editForm.hidden = true;
        if (productForm) productForm.hidden = true;

        const becomeSellerButton = document.querySelector("#becomeSellerButton");
        becomeSellerButton?.addEventListener("click", async () => {
          const oldLabel = becomeSellerButton.textContent;
          becomeSellerButton.disabled = true;
          becomeSellerButton.textContent = "در حال انجام…";
          try {
            await api("/api/auth/become-seller", { method: "POST" });
            window.location.reload();
          } catch (error) {
            notify(error.message || "تبدیل حساب انجام نشد.");
            becomeSellerButton.disabled = false;
            becomeSellerButton.textContent = oldLabel;
          }
        });
        return;
      }

      const mine = await api("/api/my/store");
      const store = mine.item;
      if (!store) {
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
        if (editForm && store) {
          ["name", "category", "city", "description", "address", "latitude", "longitude"].forEach((key) => {
            if (editForm.elements[key]) editForm.elements[key].value = store[key] ?? "";
          });
        }
        if (status)
          status.innerHTML =
            "<strong>" +
            escapeHTML(store.name) +
            "</strong><br>" +
            escapeHTML(store.city);
        if (createForm) createForm.hidden = true;
        if (editForm) editForm.hidden = false;
        if (productForm) productForm.hidden = false;
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
              address: createForm.address?.value.trim() || "",
              latitude: createForm.latitude?.value || null,
              longitude: createForm.longitude?.value || null,
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
              latitude: editForm.latitude?.value || null,
              longitude: editForm.longitude?.value || null,
            }),
          });
          notify("اطلاعات و موقعیت فروشگاه ذخیره شد.");
          location.reload();
        } catch (err) {
          notify(err.message || "ذخیرهٔ اطلاعات فروشگاه انجام نشد.");
        }
      });

      productForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!storeId) {
          notify("ابتدا ویترین بساز.");
          return;
        }
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
          notify("آگهی‌ات منتشر شد 🎉");
          productForm.reset();
          await loadSellerListings(storeId);
        } catch (err) {
          notify(err.message);
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

  function setupStoreLocationCapture() {
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-capture-store-location]");
      if (!button) return;
      const form = button.closest("form");
      const status = form?.querySelector("[data-location-status]");
      const latitude = form?.elements.latitude;
      const longitude = form?.elements.longitude;
      if (!form || !latitude || !longitude) return;
      if (!("geolocation" in navigator)) {
        if (status) status.textContent = "این مرورگر امکان دریافت موقعیت مکانی را ندارد؛ شهر و نشانی را وارد کن.";
        return;
      }
      button.disabled = true;
      button.textContent = "در حال دریافت موقعیت…";
      if (status) status.textContent = "لطفاً اجازهٔ دسترسی به موقعیت مکانی را در مرورگر تأیید کن.";
      navigator.geolocation.getCurrentPosition(
        (position) => {
          latitude.value = position.coords.latitude.toFixed(6);
          longitude.value = position.coords.longitude.toFixed(6);
          if (status) status.textContent = "موقعیت ثبت شد. مختصات همراه فرم ذخیره می‌شود.";
          button.disabled = false;
          button.textContent = "📍 دریافت دوبارهٔ موقعیت";
        },
        (error) => {
          const messages = {
            1: "اجازهٔ موقعیت مکانی داده نشد؛ از تنظیمات مرورگر اجازه بده یا شهر و نشانی را وارد کن.",
            2: "موقعیت فعلاً در دسترس نیست؛ GPS یا سرویس مکان‌یابی دستگاه را بررسی کن.",
            3: "دریافت موقعیت بیش از حد طول کشید؛ دوباره تلاش کن.",
          };
          if (status) status.textContent = messages[error.code] || "دریافت موقعیت ناموفق بود؛ شهر و نشانی را وارد کن.";
          button.disabled = false;
          button.textContent = "📍 تلاش دوباره برای ثبت موقعیت";
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
      );
    });
  }

  function setupLivePreview() {
    const form = document.querySelector("#sellerProductForm");
    if (!form) return;
    let preview = document.querySelector("#sellerLivePreview");
    if (!preview) {
      preview = document.createElement("div");
      preview.id = "sellerLivePreview";
      preview.className = "seller-live-preview";
      preview.innerHTML =
        '<span class="seller-live-preview-label">پیش‌نمایش زنده</span>' +
        '<div class="seller-live-preview-card">' +
        "<strong id=\"previewTitle\">عنوان کالا اینجا دیده می‌شود</strong>" +
        '<small id="previewMeta">شهر · دسته</small>' +
        '<span class="preview-price" id="previewPrice">قیمت</span>' +
        '<p id="previewDesc" style="margin:0;color:#64748B;font-size:.82rem;line-height:1.6">توضیح کوتاه کالا</p>' +
        "</div>";
      form.appendChild(preview);
    }
    const titleEl = preview.querySelector("#previewTitle");
    const metaEl = preview.querySelector("#previewMeta");
    const priceEl = preview.querySelector("#previewPrice");
    const descEl = preview.querySelector("#previewDesc");
    const update = () => {
      const title = (form.title?.value || form.querySelector("[name=title]")?.value || "").trim();
      const city = (form.city?.value || document.querySelector("#storeEditForm [name=city]")?.value || "شهر").trim();
      const cat = form.category?.selectedOptions?.[0]?.textContent || form.category?.value || "دسته";
      const priceRaw = form.price?.value || form.querySelector("[name=price]")?.value || "";
      const desc = (form.description?.value || form.querySelector("[name=description]")?.value || "").trim();
      if (titleEl) titleEl.textContent = title || "عنوان کالا اینجا دیده می‌شود";
      if (metaEl) metaEl.textContent = city + " · " + cat;
      if (priceEl) {
        const n = Number(String(priceRaw).replace(/[^\d.]/g, ""));
        priceEl.textContent = n > 0 ? fmt.format(n) + " تومان" : "توافقی";
      }
      if (descEl) descEl.textContent = desc || "توضیح کوتاه کالا";
    };
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    update();
  }

  Promise.resolve(initSeller()).finally(setupLivePreview);
})();
