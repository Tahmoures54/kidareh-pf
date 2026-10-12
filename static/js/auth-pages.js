(() => {
  const root = document.querySelector(".auth-page");
  if (!root) return;

  const mode = root.dataset.authMode || "login"; // login | register
  const query = new URLSearchParams(window.location.search);
  const rawNext = query.get("next") || "";
  const requestedNext =
    rawNext.startsWith("/") && !rawNext.startsWith("//") && !rawNext.includes("\\")
      ? rawNext
      : "";
  const authUrl = (path) => {
    const params = new URLSearchParams();
    if (requestedNext) params.set("next", requestedNext);
    return path + (params.size ? "?" + params.toString() : "");
  };

  // Keep the intended destination when switching between login and registration.
  document.querySelectorAll('a[href="/login"], a[href="/register"]').forEach((link) => {
    link.href = authUrl(link.getAttribute("href"));
  });
  const form = document.querySelector("#authPageForm");
  if (!form) return;

  const phoneStep = document.querySelector("#authPhoneStep");
  const codeStep = document.querySelector("#authCodeStep");
  const profileStep = document.querySelector("#authProfileStep");
  const roleStep = document.querySelector("#authRoleStep");
  const captchaQuestion = document.querySelector("#captchaQuestion");
  const feedback = document.querySelector("#authFeedback");
  const tokenMeta = document.querySelector('meta[name="csrf-token"]');
  const sellerDetails = document.querySelector("#sellerDetails");
  const buyerDetails = document.querySelector("#buyerDetails");
  const stepsIndicator = document.querySelector(
    mode === "register" ? "#registerStepsIndicator" : "#loginStepsIndicator"
  );

  let busy = false;
  let currentStep = mode === "register" ? "role" : "phone";

  const digits = (value) =>
    String(value || "").replace(/[۰-۹٠-٩]/g, (ch) =>
      String("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩".indexOf(ch) % 10)
    );

  function message(text, isError = false) {
    if (!feedback) return;
    feedback.textContent = text || "";
    feedback.classList.toggle("success", Boolean(text) && !isError);
    feedback.style.color = isError ? "#B91C1C" : "#0E7490";
  }

  async function api(path, payload) {
    const response = await fetch("/api/auth/" + path, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRF-Token": tokenMeta?.content || "",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || "درخواست انجام نشد. دوباره تلاش کنید.");
    }
    return data;
  }

  async function loadChallenge() {
    if (!captchaQuestion) return;
    try {
      const response = await fetch("/api/auth/challenge", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      captchaQuestion.textContent = data.question || "پاسخ محاسبه امنیتی را وارد کنید";
    } catch {
      captchaQuestion.textContent = "بارگذاری محاسبه امنیتی ناموفق بود؛ صفحه را تازه‌سازی کنید.";
    }
  }

  function updateStepsIndicator(step) {
    if (!stepsIndicator) return;
    const order =
      mode === "register"
        ? ["role", "phone", "code"]
        : ["phone", "code"];
    const idx = order.indexOf(step);
    stepsIndicator.querySelectorAll(".step-dot").forEach((dot) => {
      const s = dot.dataset.step;
      const i = order.indexOf(s);
      dot.classList.toggle("active", s === step);
      dot.classList.toggle("done", i < idx);
    });
  }

  let otpAbortController = null;

  function startWebOtp() {
    if (!window.isSecureContext || !("OTPCredential" in window) || !navigator.credentials?.get) return;
    otpAbortController?.abort();
    otpAbortController = new AbortController();
    navigator.credentials.get({
      otp: { transport: ["sms"] },
      signal: otpAbortController.signal,
    }).then((credential) => {
      if (!credential?.code || currentStep !== "code") return;
      const otpInput = form.elements.otp;
      if (!otpInput) return;
      otpInput.value = digits(credential.code).slice(0, 6);
      if (otpInput.value.length === 6) form.requestSubmit();
    }).catch(() => {
      // Unsupported browsers, denied prompts, and manual entry all remain valid.
    });
  }

  function showStep(step) {
    currentStep = step;
    if (step !== "code") {
      otpAbortController?.abort();
      otpAbortController = null;
    }
    if (roleStep) roleStep.hidden = step !== "role";
    if (phoneStep) phoneStep.hidden = step !== "phone";
    if (codeStep) codeStep.hidden = step !== "code";
    if (profileStep) profileStep.hidden = step !== "profile";
    updateStepsIndicator(step);

    if (step === "phone") {
      const phoneInput = form.elements.phone;
      phoneInput?.focus();
      loadChallenge();
    } else if (step === "code") {
      form.elements.otp?.focus();
      startWebOtp();
    } else if (step === "profile") {
      form.elements.name?.focus();
      syncSellerDetails();
    }
  }

  function selectedRole() {
    const checked = form.querySelector('input[name="role"]:checked');
    return checked ? checked.value : "buyer";
  }

  function syncSellerDetails() {
    if (!sellerDetails) return;
    const isSeller = selectedRole() === "seller";
    sellerDetails.hidden = !isSeller;
    if (buyerDetails) buyerDetails.hidden = isSeller;
    const buyerCity = form.elements.city;
    if (buyerCity) buyerCity.required = !isSeller;
    ["store_name", "store_city"].forEach((name) => {
      const el = form.elements[name];
      if (el) el.required = isSeller;
    });
  }

  document.querySelector("#continueRoleButton")?.addEventListener("click", () => {
    message("");
    showStep("phone");
  });

  document.querySelector("#backToRoleButton")?.addEventListener("click", () => {
    message("");
    showStep("role");
  });

  document.querySelector("#backToPhoneButton")?.addEventListener("click", async () => {
    message("");
    if (form.elements.otp) form.elements.otp.value = "";
    if (form.elements.captcha) form.elements.captcha.value = "";
    showStep("phone");
  });

  form.querySelectorAll('input[name="role"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      if (currentStep === "profile") syncSellerDetails();
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    busy = true;

    const submitButtons = [...form.querySelectorAll("button[type=submit]")];
    const labels = submitButtons.map((b) => b.textContent);
    submitButtons.forEach((b) => {
      b.disabled = true;
      b.textContent = "در حال انجام…";
    });

    try {
      if (currentStep === "phone") {
        const accepted = true; // Acceptance is communicated by continuing after the visible terms notice.
        const phone = digits(form.elements.phone?.value).trim();
        const captcha = digits(form.elements.captcha?.value).trim();

        const data = await api("request-otp", {
          phone,
          captcha_answer: captcha,
          terms_accepted: accepted,
          registering: mode === "register",
          role: selectedRole(),
        });

        const label = document.querySelector("#otpPhoneLabel");
        if (label) label.textContent = form.elements.phone.value.trim();
        showStep("code");
        message(data.message || "کد تأیید ارسال شد.");
      } else if (currentStep === "code") {
        const code = digits(form.elements.otp?.value).trim();
        const data = await api("verify-otp", { code });

        if (data.existing_user && data.user) {
          if (tokenMeta && data.csrf_token) tokenMeta.content = data.csrf_token;
          message("ورود موفق بود؛ در حال انتقال…");
          const destination =
            requestedNext || (data.user.role === "seller" ? "/seller" : "/");
          window.location.assign(destination);
          return;
        }

        if (data.phone) {
          if (mode === "login") {
            message("حسابی با این شماره یافت نشد. در حال انتقال به ثبت‌نام…");
            setTimeout(() => {
              window.location.assign(authUrl("/register"));
            }, 1200);
            return;
          }
          showStep("profile");
          message("شماره تأیید شد؛ اطلاعات حساب را تکمیل کنید.");
        }
      } else if (currentStep === "profile") {
        const role = selectedRole();
        const payload = {
          name: (form.elements.name?.value || "").trim(),
          role,
          city: (form.elements.city?.value || "").trim(),
          store_name: (form.elements.store_name?.value || "").trim(),
          store_category: (form.elements.store_category?.value || "").trim(),
          store_city: (form.elements.store_city?.value || "").trim(),
          contact_name: (form.elements.contact_name?.value || "").trim(),
          store_address: (form.elements.store_address?.value || "").trim(),
          store_hours: (form.elements.store_hours?.value || "").trim(),
          store_description: (form.elements.store_description?.value || "").trim(),
          in_person: Boolean(form.elements.in_person?.checked),
        };

        const data = await api("complete-profile", payload);
        if (tokenMeta && data.csrf_token) tokenMeta.content = data.csrf_token;
        message("حساب شما ساخته شد؛ خوش آمدید!");
        const destination =
          requestedNext && (role === "seller" || requestedNext !== "/seller")
            ? requestedNext
            : role === "seller"
              ? "/seller"
              : "/account";
        window.location.assign(destination);
        return;
      }
    } catch (error) {
      message(error.message || "ارتباط برقرار نشد، دوباره امتحان می‌کنیم؟", true);
      if (
        currentStep === "phone" &&
        /محاسبه|captcha|پاسخ/i.test(error.message || "")
      ) {
        if (form.elements.captcha) form.elements.captcha.value = "";
        await loadChallenge();
      }
    } finally {
      busy = false;
      submitButtons.forEach((b, i) => {
        b.disabled = false;
        b.textContent = labels[i];
      });
    }
  });

  // showStep() already loads the challenge when the initial step is "phone".
  // Avoid a second parallel request that can invalidate the challenge the user sees.
  showStep(currentStep);
})();
