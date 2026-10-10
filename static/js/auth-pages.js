(() => {
  const root = document.querySelector(".auth-page");
  if (!root) return;

  const mode = root.dataset.authMode || "login"; // login | register
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
        ? ["role", "phone", "code", "profile"]
        : ["phone", "code"];
    const idx = order.indexOf(step);
    stepsIndicator.querySelectorAll(".step-dot").forEach((dot) => {
      const s = dot.dataset.step;
      const i = order.indexOf(s);
      dot.classList.toggle("active", s === step);
      dot.classList.toggle("done", i < idx);
    });
  }

  function showStep(step) {
    currentStep = step;
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
        const accepted = Boolean(form.elements.terms_accepted?.checked);
        if (!accepted) throw new Error("برای ادامه، پذیرش قوانین را علامت بزنید.");

        const phone = digits(form.elements.phone?.value).trim();
        const captcha = digits(form.elements.captcha?.value).trim();

        const data = await api("request-otp", {
          phone,
          captcha_answer: captcha,
          terms_accepted: accepted,
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
          const redirect =
            data.user.role === "seller" ? "/seller" : "/account";
          window.location.assign(redirect);
          return;
        }

        if (data.phone) {
          if (mode === "login") {
            message("حسابی با این شماره یافت نشد. در حال انتقال به ثبت‌نام…");
            setTimeout(() => {
              window.location.assign("/register");
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
        window.location.assign(role === "seller" ? "/seller" : "/account");
        return;
      }
    } catch (error) {
      message(error.message || "خطایی رخ داد؛ دوباره تلاش کنید.", true);
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

  showStep(currentStep);
  if (currentStep === "phone") loadChallenge();
})();
