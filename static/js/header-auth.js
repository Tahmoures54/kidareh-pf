(() => {
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const loginLink = document.querySelector("#headerLoginLink");
  const registerLink = document.querySelector("#headerRegisterLink");
  const accountLink = document.querySelector("#headerAccountLink");
  const logoutButton = document.querySelector("#headerLogoutButton");
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
