(() => {
  const dialog=document.querySelector("#authDialog"), openButton=document.querySelector("#loginButton"), closeButton=document.querySelector("#closeAuthDialog"), form=document.querySelector("#authForm");
  if(!dialog||!openButton||!form)return;
  const phoneStep=document.querySelector("#authPhoneStep"), codeStep=document.querySelector("#authCodeStep"), profileStep=document.querySelector("#authProfileStep");
  const captchaQuestion=document.querySelector("#captchaQuestion"), feedback=document.querySelector("#authFeedback"), phoneInput=form.elements.phone, captchaInput=form.elements.captcha, otpInput=form.elements.otp, tokenMeta=document.querySelector('meta[name="csrf-token"]');
  let busy=false;
  const digits=value=>String(value||"").replace(/[۰-۹٠-٩]/g,ch=>String("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩".indexOf(ch)%10));
  function message(text,error=false){if(feedback){feedback.textContent=text;feedback.style.color=error?"#B91C1C":"#0E7490";}}
  async function api(path,payload){const response=await fetch("/api/auth/"+path,{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","Accept":"application/json","X-CSRF-Token":tokenMeta?.content||""},body:JSON.stringify(payload)});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.message||"درخواست انجام نشد. دوباره تلاش کنید.");return data;}
  async function loadChallenge(){try{const response=await fetch("/api/auth/challenge",{credentials:"same-origin",headers:{Accept:"application/json"},cache:"no-store"});if(!response.ok)throw new Error();const data=await response.json();captchaQuestion.textContent=data.question||"پاسخ محاسبه امنیتی را وارد کنید";}catch{captchaQuestion.textContent="بارگذاری محاسبه امنیتی ناموفق بود؛ صفحه را تازه‌سازی کنید.";}}
  function showStep(step){phoneStep.hidden=step!=="phone";codeStep.hidden=step!=="code";profileStep.hidden=step!=="profile";}
  openButton.addEventListener("click",async()=>{message("");if(typeof dialog.showModal==="function")dialog.showModal();else dialog.setAttribute("open","");await loadChallenge();phoneInput.focus();});
  closeButton?.addEventListener("click",()=>dialog.close());
  dialog.addEventListener("click",event=>{if(event.target===dialog&&typeof dialog.close==="function")dialog.close();});
  document.querySelector("#backToPhoneButton")?.addEventListener("click",async()=>{showStep("phone");otpInput.value="";captchaInput.value="";message("");await loadChallenge();});
  form.elements.role?.addEventListener("change",event=>{const sellerDetails=document.querySelector("#sellerDetails");if(sellerDetails)sellerDetails.hidden=event.target.value!=="seller";});
  form.addEventListener("submit",async event=>{
    event.preventDefault();if(busy)return;busy=true;
    const buttons=[...form.querySelectorAll("button[type=submit]")], labels=buttons.map(button=>button.textContent);
    buttons.forEach(button=>{button.disabled=true;button.textContent="در حال انجام…";});
    try{
      if(!phoneStep.hidden){
        const accepted=Boolean(form.elements.terms_accepted?.checked);if(!accepted)throw new Error("برای ادامه، پذیرش قوانین را علامت بزنید.");
        const data=await api("request-otp",{phone:digits(phoneInput.value).trim(),captcha_answer:digits(captchaInput.value).trim(),terms_accepted:accepted});
        document.querySelector("#otpPhoneLabel").textContent=phoneInput.value.trim();showStep("code");otpInput.focus();message(data.message||"کد تأیید ارسال شد.");
      }else if(!codeStep.hidden){
        const data=await api("verify-otp",{code:digits(otpInput.value).trim()});
        if(data.existing_user&&data.user){if(tokenMeta&&data.csrf_token)tokenMeta.content=data.csrf_token;message("ورود موفق بود؛ در حال باز کردن حساب…");window.location.assign("/account");return;}
        if(data.phone){showStep("profile");form.elements.name?.focus();message("شماره تأیید شد؛ اطلاعات حساب را تکمیل کنید.");}
      }else{
        const payload={name:form.elements.name.value.trim(),role:form.elements.role.value,store_name:form.elements.store_name?.value.trim()||"",store_category:form.elements.store_category?.value.trim()||"",store_city:form.elements.store_city?.value.trim()||"",contact_name:form.elements.contact_name?.value.trim()||"",store_address:form.elements.store_address?.value.trim()||""};
        const data=await api("complete-profile",payload);if(tokenMeta&&data.csrf_token)tokenMeta.content=data.csrf_token;message("حساب شما ساخته شد؛ خوش آمدید!");window.location.assign(payload.role==="seller"?"/seller":"/account");return;
      }
    }catch(error){message(error.message||"خطایی رخ داد؛ دوباره تلاش کنید.",true);if(!phoneStep.hidden&&/محاسبه|captcha|پاسخ/i.test(error.message||"")){captchaInput.value="";await loadChallenge();}}
    finally{busy=false;buttons.forEach((button,i)=>{button.disabled=false;button.textContent=labels[i];});}
  });
  loadChallenge();
})();