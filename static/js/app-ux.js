(() => {
  "use strict";
  const numberFormat = new Intl.NumberFormat("fa-IR");
  const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  function setNearbyBanner(visible) {
    const banner = document.querySelector("#nearbyActiveBanner");
    if (!banner) return;
    banner.classList.toggle("is-visible", Boolean(visible));
  }

  function enhanceListingCards() {
    document.querySelectorAll(".listing-card .listing-body, .page-listing-body").forEach((body) => {
      if (body.querySelector(".trust-badge-row")) return;
      const footer = body.querySelector(".listing-footer strong, .page-listing-footer strong");
      const priceText = footer?.textContent || "";
      const isApprox = priceText.includes("تومان");
      const row = document.createElement("div");
      row.className = "trust-badge-row";
      row.innerHTML = isApprox
        ? '<span class="trust-badge trust-badge-price" title="قیمت اعلام‌شده؛ قبل از مراجعه هماهنگ کنید">≈ تقریبی</span>'
        : '<span class="trust-badge trust-badge-price">توافقی</span>';
      const footerEl = body.querySelector(".listing-footer, .page-listing-footer");
      if (footerEl) body.insertBefore(row, footerEl);
      else body.appendChild(row);
    });
  }

  const grids = [document.querySelector("#listingGrid"), document.querySelector("#pageListings")].filter(Boolean);
  grids.forEach((grid) => {
    const mo = new MutationObserver(() => enhanceListingCards());
    mo.observe(grid, { childList: true, subtree: true });
  });
  enhanceListingCards();

  window.setTimeout(() => {
    const findBtn = document.querySelector("#findMyLocationButton");
    const nearbyBtn = document.querySelector("#nearbyListingsButton");
    const clearNearby = document.querySelector("#clearNearbyMode");
    const emptyTry = document.querySelector("#emptyTryNearby");
    const citySelect = document.querySelector("#citySelect");

    clearNearby?.addEventListener("click", () => {
      setNearbyBanner(false);
      if (findBtn) findBtn.innerHTML = '<span aria-hidden="true">◎</span> پیدا کردن کالاهای اطراف من';
      citySelect?.dispatchEvent(new Event("change", { bubbles: true }));
    });

    emptyTry?.addEventListener("click", () => {
      (findBtn || nearbyBtn)?.click();
    });

    if (findBtn) {
      const btnMo = new MutationObserver(() => {
        const t = findBtn.textContent || "";
        if (t.includes("موقعیت") || t.includes("فعال") || t.includes("✓")) {
          setNearbyBanner(true);
        }
      });
      btnMo.observe(findBtn, { childList: true, characterData: true, subtree: true });
    }
  }, 500);
})();
