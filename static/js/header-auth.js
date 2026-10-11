(() => {
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const loginLink = document.querySelector("#headerLoginLink");
  const registerLink = document.querySelector("#headerRegisterLink");
  const accountLink = document.querySelector("#headerAccountLink");
  const logoutButton = document.querySelector("#headerLogoutButton");
  const legalLinks = document.querySelector("#legalLinks");
  if (!loginLink || !registerLink || !accountLink || !logoutButton) return;

  const setVisible = (element, visible) => {
    element.hidden = !visible;
    element.style.display = visible ? "" : "none";
  };
  const toast = (message) => {
    const target = document.querySelector("#pageToast");
    if (target) {
      target.textContent = message;
      target.classList.add("visible");
      window.setTimeout(() => target.classList.remove("visible"), 2600);
    } else {
      window.alert(message);
    }
  };

  fetch("/api/auth/me", { headers: { Accept: "application/json" }, credentials: "same-origin" })
    .then((response) => response.ok ? response.json() : Promise.reject(new Error("وضعیت حساب بررسی نشد.")))
    .then((data) => {
      const signedIn = Boolean(data.user);
      setVisible(loginLink, !signedIn);
      setVisible(registerLink, !signedIn);
      setVisible(accountLink, signedIn);
      setVisible(logoutButton, signedIn);
      if (legalLinks) setVisible(legalLinks, signedIn);

      // A guest has no account yet: protected actions start the registration
      // flow, while the intended internal destination survives OTP verification.
      document.querySelectorAll(
        'a[href^="/seller"], a[href="/monetization"], a[href="/account"], ' +
        'a[href="/saved"], a[href="/following"], a[href="/messages"], ' +
        'a[href="/support"], a[href="/admin"], a[href="/admin/reports"]'
      ).forEach((link) => {
        if (signedIn) return;
        const target = new URL(link.getAttribute("href"), window.location.origin);
        link.href = "/register?next=" + encodeURIComponent(target.pathname + target.search);
      });
    })
    .catch(() => {
      // Keep guest navigation visible if session verification is temporarily unavailable.
    });

  logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;
    const originalText = logoutButton.textContent;
    logoutButton.textContent = "در حال خروج…";
    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRF-Token": token },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message || data.error || "خروج انجام نشد.");
      window.location.assign("/");
    } catch (error) {
      toast(error.message || "خروج انجام نشد؛ دوباره تلاش کنید.");
      logoutButton.disabled = false;
      logoutButton.textContent = originalText;
    }
  });
})();
