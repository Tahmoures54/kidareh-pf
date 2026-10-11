(() => {
  "use strict";
  /* Enhance product/store cards on search/list pages after pages.js renders */
  function enhance() {
    document.querySelectorAll(".page-listing-body").forEach((body) => {
      if (body.querySelector(".trust-badge-row")) return;
      const strong = body.querySelector(".page-listing-footer strong");
      const isApprox = (strong?.textContent || "").includes("تومان");
      const row = document.createElement("div");
      row.className = "trust-badge-row";
      row.innerHTML = isApprox
        ? '<span class="trust-badge trust-badge-price">≈ تقریبی</span>'
        : '<span class="trust-badge trust-badge-price">توافقی</span>';
      const footer = body.querySelector(".page-listing-footer");
      if (footer) body.insertBefore(row, footer);
    });
    document.querySelectorAll(".page-store-copy").forEach((copy) => {
      if (copy.querySelector(".trust-badge-row")) return;
      const badge = copy.querySelector(".store-paid-badge");
      if (!badge) return;
      const row = document.createElement("div");
      row.className = "trust-badge-row";
      row.style.marginTop = ".4rem";
      row.innerHTML = '<span class="trust-badge trust-badge-verified">✓ تیک آبی</span>';
      copy.appendChild(row);
    });
  }
  const target = document.querySelector("#pageListings");
  if (target) {
    new MutationObserver(enhance).observe(target, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhance);
  else enhance();
})();
