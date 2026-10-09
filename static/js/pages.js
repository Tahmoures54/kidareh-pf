(() => {
  const page = window.KIDAREH_PAGE || {};
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const toast = document.querySelector("#pageToast");
  const fmt = new Intl.NumberFormat("fa-IR");
  const savedKey = "kidareh-saved-products";
  const escapeHTML = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const categoryNames = {home:"خانه و زندگی",digital:"دیجیتال",fashion:"پوشاک",vehicle:"خودرو",services:"خدمات",other:"سایر"};
  function notify(message){if(!toast)return;toast.textContent=message;toast.classList.add("visible");window.setTimeout(()=>toast.classList.remove("visible"),2600);}
  async function api(url, options={}) {
    const headers = {Accept:"application/json", ...(options.headers||{})};
    if(options.method && options.method !== "GET") headers["X-CSRF-Token"] = token;
    const response = await fetch(url,{...options,headers});
    const data = await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(data.message || data.error || "درخواست انجام نشد.");
    return data;
  }
  function productCard(item){
    const price = Number(item.price)>0 ? fmt.format(item.price)+" تومان" : "قیمت توافقی";
    const art = item.image_path ? '<img src="'+escapeHTML(item.image_path)+'" alt="'+escapeHTML(item.title)+'" loading="lazy">' : '<span>'+escapeHTML(item.emoji||"🛍️")+'</span>';
    return '<article class="page-listing-card"><a class="page-listing-art" href="/product/'+item.id+'" aria-label="'+escapeHTML(item.title)+'">'+art+'</a><div class="page-listing-body"><div class="page-listing-meta"><span>'+escapeHTML(item.city)+'</span><span>·</span><span>'+escapeHTML(categoryNames[item.category]||"کالا")+'</span></div><h3>'+escapeHTML(item.title)+'</h3><p>'+escapeHTML(item.description||"برای اطلاعات بیشتر، جزئیات کالا را ببین.")+'</p><div class="page-listing-footer"><strong>'+price+'</strong><a href="/product/'+item.id+'">جزئیات ←</a><button type="button" data-save="'+item.id+'">♡ ذخیره</button><button class="share-button" type="button" data-share-url="/product/'+item.id+'" data-share-title="کالای '+escapeHTML(item.title)+'" aria-label="اشتراک‌گذاری کالا" title="اشتراک‌گذاری کالا">↗</button></div></div></article>';
  }
  function storeCard(store){
    return '<article class="page-store-card"><a class="page-store-card-link" href="/store/'+store.id+'"><span class="page-store-mark">⌂</span><span class="page-store-copy"><strong>'+escapeHTML(store.name)+'</strong><small>'+escapeHTML(store.city)+' · '+fmt.format(store.product_count||0)+' کالا · '+fmt.format(store.follower_count||0)+' دنبال‌کننده</small><p>'+escapeHTML(store.description||"برای دیدن کالاهای این فروشگاه وارد ویترین شو.")+'</p></span></a><button class="share-button" type="button" data-share-url="/store/'+store.id+'" data-share-title="ویترین '+escapeHTML(store.name)+'" aria-label="اشتراک‌گذاری ویترین" title="اشتراک‌گذاری ویترین">↗ معرفی ویترین</button></article>';
  }
  async function loadListings(container, params={}) {
    const target=document.querySelector(container); if(!target)return;
    target.innerHTML='<div class="loading-card">در حال دریافت کالاها…</div>';
    try {
      const qs=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>{if(v)qs.set(k,v)});
      const data=await api("/api/listings?"+qs.toString());
      target.innerHTML=data.items.length?data.items.map(productCard).join(""):'<div class="empty-page-state">کالایی با این مشخصات پیدا نشد. عبارت یا فیلتر دیگری را امتحان کن.</div>';
      const count=document.querySelector("#pageResultsCount");if(count)count.textContent=fmt.format(data.items.length)+" کالا";
    } catch(e){target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>';}
  }
  async function loadStores(container, query="") {
    const target=document.querySelector(container);if(!target)return;
    try {
      const data=await api("/api/stores?"+new URLSearchParams(query?{q:query}:{}));
      target.innerHTML=data.items.length?data.items.map(storeCard).join(""):'<div class="empty-page-state">فروشگاهی پیدا نشد. نام دیگری جست‌وجو کن.</div>';
      const count=document.querySelector("#pageResultsCount");if(count)count.textContent=fmt.format(data.items.length)+" فروشگاه";
    }catch(e){target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>';}
  }
  async function initSearch(){
    const form=document.querySelector("#pageSearchForm");
    const run=()=>loadListings("#pageListings",{q:document.querySelector("#pageQuery").value.trim(),category:document.querySelector("#pageCategory").value,city:document.querySelector("#pageCity").value.trim()});
    form?.addEventListener("submit",e=>{e.preventDefault();run()}); await run();
  }
  function initStores(){
    const input=document.querySelector("#storeQuery"),form=document.querySelector("#storeSearchForm");
    const run=()=>loadStores("#pageStores",input?.value.trim()||"");
    form?.addEventListener("submit",e=>{e.preventDefault();run()});if(input)input.value=page.query||"";run();
  }
  async function initStoreDetail(){
    try{
      const data=await api("/api/stores/"+page.storeId);const s=data.store;
      document.querySelector("#storeTitle").textContent=s.name;
      document.querySelector("#storeDescription").textContent=s.description||"به ویترین این فروشگاه خوش آمدید.";
      document.querySelector("#storeMeta").textContent=s.city+" · "+fmt.format(s.product_count||0)+" کالا · "+fmt.format(s.follower_count||0)+" دنبال‌کننده";
      const contact = document.querySelector("#storeContactDetails");
      const details = [];
      if (s.category) details.push("<p><strong>حوزه فعالیت:</strong> "+escapeHTML(s.category)+"</p>");
      if (s.in_person && s.address) details.push("<p><strong>نشانی مراجعه حضوری:</strong> "+escapeHTML(s.address)+"</p>");
      if (s.hours) details.push("<p><strong>ساعات کاری:</strong> "+escapeHTML(s.hours)+"</p>");
      if (s.contact_name) details.push("<p><strong>مسئول پاسخ‌گو:</strong> "+escapeHTML(s.contact_name)+"</p>");
      if (contact) contact.innerHTML = details.join("");
      const follow=document.querySelector("#followStore");follow.textContent=data.following?"✓ دنبال می‌کنی":"♡ دنبال‌کردن فروشگاه";
      follow.addEventListener("click",async()=>{try{const me=await api("/api/auth/me");if(!me.user){notify("برای دنبال‌کردن فروشگاه ابتدا وارد حساب شو.");location.href="/account";return;}const result=await api("/api/stores/"+page.storeId+"/follow",{method:"POST"});follow.textContent=result.following?"✓ دنبال می‌کنی":"♡ دنبال‌کردن فروشگاه";document.querySelector("#storeMeta").textContent=s.city+" · "+fmt.format(s.product_count||0)+" کالا · "+fmt.format(result.follower_count||0)+" دنبال‌کننده";notify(result.following?"فروشگاه به دنبال‌شده‌ها اضافه شد.":"فروشگاه از دنبال‌شده‌ها برداشته شد.");}catch(e){notify(e.message)}});
      const target=document.querySelector("#pageListings");target.innerHTML=(data.items||[]).length?data.items.map(productCard).join(""):'<div class="empty-page-state">این ویترین هنوز کالایی ندارد.</div>';
      const count=document.querySelector("#pageResultsCount");if(count)count.textContent=fmt.format((data.items||[]).length)+" کالا";
    }catch(e){document.querySelector("#storeTitle").textContent="ویترین پیدا نشد";notify(e.message)}
  }
  async function initProductDetail(){
    try{const data=await api("/api/listings/"+page.productId);const p=data.item;
      document.querySelector("#productTitle").textContent=p.title;
      const price=Number(p.price)>0?fmt.format(p.price)+" تومان":"قیمت توافقی";
      const art=p.image_path?'<img src="'+escapeHTML(p.image_path)+'" alt="'+escapeHTML(p.title)+'">':escapeHTML(p.emoji||"🛍️");
      document.querySelector("#productDetail").innerHTML='<div class="product-detail-art">'+art+'</div><div class="product-detail-copy"><div class="page-listing-meta">'+escapeHTML(p.city)+' · '+escapeHTML(categoryNames[p.category]||"کالا")+'</div><h2>'+escapeHTML(p.title)+'</h2><strong class="product-detail-price">'+price+'</strong><p>'+escapeHTML(p.description||"توضیحی برای این کالا ثبت نشده است.")+'</p><div class="account-actions"><button id="productSave" class="button button-primary" type="button">♡ ذخیره کالا</button><button class="share-button" type="button" data-share-url="/product/'+p.id+'" data-share-title="کالای '+escapeHTML(p.title)+'">↗ اشتراک‌گذاری کالا</button>'+(p.store_id?'<a class="button button-outline" href="/store/'+p.store_id+'">مشاهده فروشگاه</a>':'')+'</div>'+(p.seller_phone?'<p><a class="button button-outline" href="tel:'+escapeHTML(p.seller_phone)+'">تماس با فروشنده</a></p>':'')+'</div>';
      document.querySelector("#productSave").addEventListener("click",()=>saveProduct(p.id));
    }catch(e){document.querySelector("#productDetail").innerHTML='<div class="empty-page-state">این کالا پیدا نشد یا حذف شده است.</div>';}
  }
  async function saveProduct(id){
    try{
      const me=await api("/api/auth/me");
      if(me.user){
        const result=await api("/api/listings/"+encodeURIComponent(id)+"/save",{method:"POST"});
        notify(result.saved?"کالا به ذخیره‌های حساب اضافه شد.":"کالا از ذخیره‌های حساب برداشته شد.");
        if(page.type==="saved")await initSaved();
        return result.saved;
      }
    }catch(e){if(e.message!=="authentication_required"){notify(e.message);return false;}}
    let ids=[];try{ids=JSON.parse(localStorage.getItem(savedKey)||"[]").map(String)}catch{}
    const set=new Set(ids);const key=String(id);if(set.has(key))set.delete(key);else set.add(key);
    try{localStorage.setItem(savedKey,JSON.stringify([...set]));}catch{notify("ذخیره محلی در این مرورگر در دسترس نیست.");return false;}
    notify(set.has(key)?"کالا ذخیره شد.":"کالا از ذخیره‌ها حذف شد.");if(page.type==="saved")await initSaved();return set.has(key);
  }
  async function initSaved(){
    const target=document.querySelector("#pageListings");if(!target)return;
    target.innerHTML='<div class="loading-card">در حال بارگذاری ذخیره‌ها…</div>';
    let user=null,items=[];
    try{const me=await api("/api/auth/me");user=me.user;}catch{}
    if(user){
      try{const data=await api("/api/products/saved");items=data.items||[];}
      catch(e){target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>';return;}
    }else{
      let ids=[];try{ids=JSON.parse(localStorage.getItem(savedKey)||"[]").map(String)}catch{}
      for(const id of ids){try{const d=await api("/api/listings/"+encodeURIComponent(id));if(d.item)items.push(d.item)}catch{}}
    }
    target.innerHTML=items.length?items.map(productCard).join(""):'<div class="empty-page-state">هنوز کالایی ذخیره نکرده‌ای. در صفحه جست‌وجو روی «ذخیره» بزن تا اینجا پیدایش کنی.</div>';
    const hint=document.querySelector("#savedHint");if(hint)hint.textContent=user?"این فهرست به حساب شما متصل است و با ورود از دستگاه‌های دیگر هم در دسترس خواهد بود.":"ذخیره‌های مهمان فقط روی همین مرورگر و دستگاه نگهداری می‌شوند.";
    const clear=document.querySelector("#clearSaved");if(clear){clear.textContent=user?"پاک‌کردن همه ذخیره‌ها":"پاک‌کردن ذخیره‌های این دستگاه";clear.onclick=async()=>{if(!items.length){if(!user){try{localStorage.removeItem(savedKey)}catch{}}notify("فهرست ذخیره‌ها خالی است.");return;}if(!window.confirm("همه کالاهای ذخیره‌شده حذف شوند؟"))return;try{if(user){for(const item of items)await api("/api/listings/"+item.id+"/save",{method:"POST"});}else{localStorage.removeItem(savedKey);}notify("ذخیره‌ها پاک شدند.");await initSaved();}catch(e){notify(e.message)}};}
  }
  async function initFollowing(){
    const target=document.querySelector("#pageStores");if(!target)return;
    try{const me=await api("/api/auth/me");if(!me.user){target.innerHTML='<div class="empty-page-state">برای دیدن فروشگاه‌های دنبال‌شده، <a href="/account">وارد حساب شو</a>. البته دیدن بقیه بازار آزاد است.</div>';return}
      const data=await api("/api/stores/following");
      target.innerHTML=data.items.length?data.items.map(s=>'<div class="following-store-row">'+storeCard(s)+'<button class="button button-outline" type="button" data-unfollow-store="'+s.id+'">برداشتن دنبال‌کردن</button></div>').join(""):'<div class="empty-page-state">هنوز فروشگاهی را دنبال نکرده‌ای. از صفحه فروشگاه‌ها شروع کن.</div>';
      target.onclick=async e=>{const button=e.target.closest("[data-unfollow-store]");if(!button)return;button.disabled=true;try{await api("/api/stores/"+button.dataset.unfollowStore+"/follow",{method:"POST"});notify("فروشگاه از فهرست دنبال‌شده‌ها حذف شد.");await initFollowing();}catch(err){notify(err.message);button.disabled=false;}};
    }catch(e){target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>'}
  }
  async function initAccount(){
    const status=document.querySelector("#accountStatus"),actions=document.querySelector("#accountActions");
    try{const data=await api("/api/auth/me");if(data.user){status.innerHTML='<strong>سلام '+escapeHTML(data.user.name)+'!</strong><br>شماره همراه: '+escapeHTML(data.user.phone)+'<br>نوع حساب: '+(data.user.role==="seller"?"فروشنده":"خریدار");actions.innerHTML='<a class="button button-primary" href="/seller">مدیریت ویترین</a><a class="button button-outline" href="/saved">محصولات ذخیره‌شده</a><button id="logoutButton" class="button button-outline" type="button">خروج از حساب</button>';document.querySelector("#logoutButton").addEventListener("click",async()=>{try{await api("/api/auth/logout",{method:"POST"});location.reload()}catch(e){notify(e.message)}})}else{status.textContent="هنوز وارد حساب نشده‌ای. برای گشتن در بازار نیازی به حساب نیست.";actions.innerHTML='<a class="button button-primary" href="/?auth=signup">ورود یا ثبت‌نام</a><a class="button button-outline" href="/seller">ساخت ویترین فروشگاه</a>'}}catch(e){status.textContent="وضعیت حساب در دسترس نیست."}
  }
  async function initSeller(){
    const status=document.querySelector("#sellerStatus"),createForm=document.querySelector("#storeCreateForm"),editForm=document.querySelector("#storeEditForm"),target=document.querySelector("#pageListings");let store=null;
    const categoryOptions=Object.entries(categoryNames).map(([id,name])=>'<option value="'+id+'">'+escapeHTML(name)+'</option>').join("");
    function renderProducts(items){
      const count=document.querySelector("#pageResultsCount");if(count)count.textContent=fmt.format(items.length)+" کالا";
      if(!items.length){target.innerHTML='<div class="empty-page-state">هنوز محصولی در ویترینت نیست. از دکمه افزودن محصول استفاده کن.</div>';return;}
      target.innerHTML=items.map(p=>'<article class="page-panel seller-product-manage" data-product="'+p.id+'"><div class="page-listing-body"><div class="page-listing-meta">'+escapeHTML(p.city)+' · '+escapeHTML(categoryNames[p.category]||"کالا")+'</div><h3>'+escapeHTML(p.title)+'</h3><p>'+escapeHTML(p.description||"")+'</p><div class="page-listing-footer"><strong>'+(Number(p.price)>0?fmt.format(p.price)+" تومان":"قیمت توافقی")+'</strong><button class="button button-outline" type="button" data-edit-product="'+p.id+'">ویرایش</button><button class="button button-outline" type="button" data-delete-product="'+p.id+'">حذف</button></div><form class="stack-form seller-product-edit" data-edit-form="'+p.id+'" hidden><label>عنوان<input name="title" required maxlength="100" value="'+escapeHTML(p.title)+'"></label><label>دسته‌بندی<select name="category">'+categoryOptions+'</select></label><label>شهر<input name="city" required maxlength="60" value="'+escapeHTML(p.city)+'"></label><label>قیمت به تومان<input name="price" type="number" min="0" max="1000000000000" required value="'+Number(p.price||0)+'"></label><label>توضیحات<textarea name="description" rows="3" maxlength="1000">'+escapeHTML(p.description||"")+'</textarea></label><label>شماره تماس فروشنده<input name="seller_phone" inputmode="numeric" maxlength="11" value="'+escapeHTML(p.seller_phone||"")+'" placeholder="09123456789"></label><button class="button button-primary" type="submit">ذخیره محصول</button></form></div></article>').join("");
      items.forEach(p=>{const select=target.querySelector('[data-edit-form="'+p.id+'"] select[name="category"]');if(select)select.value=p.category;});
    }
    try{
      const me=await api("/api/auth/me");if(!me.user){status.innerHTML='برای مدیریت ویترین، ابتدا <a href="/account">وارد حساب شو</a>. دیدن محصولات و فروشگاه‌ها بدون حساب آزاد است.';return;}
      const storeData=await api("/api/my/store");store=storeData.item;
      if(store){status.innerHTML='<strong>'+escapeHTML(store.name)+'</strong><br>'+escapeHTML(store.city)+' · ویترین فعال';createForm.hidden=true;editForm.hidden=false;editForm.elements.name.value=store.name;editForm.elements.city.value=store.city;editForm.elements.description.value=store.description||"";const listings=await api("/api/listings");renderProducts((listings.items||[]).filter(p=>Number(p.store_id)===Number(store.id)));}
      else{status.textContent=me.user.role==="seller"?"حساب فروشنده فعال است؛ ویترینت را بساز.":"برای ساخت ویترین، حساب شما به فروشنده تبدیل می‌شود.";createForm.hidden=false;editForm.hidden=true;target.innerHTML='<div class="empty-page-state">برای مدیریت محصولات، ابتدا ویترین خودت را بساز.</div>';}
      createForm.addEventListener("submit",async e=>{e.preventDefault();try{if(me.user.role!=="seller")await api("/api/auth/become-seller",{method:"POST"});const body=Object.fromEntries(new FormData(createForm));await api("/api/stores",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});notify("ویترین ساخته شد.");location.href="/seller";}catch(err){notify(err.message)}});
      editForm.addEventListener("submit",async e=>{e.preventDefault();try{const body=Object.fromEntries(new FormData(editForm));const result=await api("/api/stores/"+store.id,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});store=result.item;status.innerHTML='<strong>'+escapeHTML(store.name)+'</strong><br>'+escapeHTML(store.city)+' · ویترین فعال';notify("اطلاعات ویترین ذخیره شد.");}catch(err){notify(err.message)}});
      target.addEventListener("click",async e=>{const edit=e.target.closest("[data-edit-product]");if(edit){const form=target.querySelector('[data-edit-form="'+edit.dataset.editProduct+'"]');if(form)form.hidden=!form.hidden;return;}const remove=e.target.closest("[data-delete-product]");if(remove){if(!window.confirm("این محصول حذف شود؟ این کار قابل بازگشت نیست."))return;remove.disabled=true;try{await api("/api/listings/"+remove.dataset.deleteProduct,{method:"DELETE"});notify("محصول حذف شد.");const data=await api("/api/listings");renderProducts((data.items||[]).filter(p=>Number(p.store_id)===Number(store.id)));}catch(err){notify(err.message);remove.disabled=false;}}});
      target.addEventListener("submit",async e=>{const form=e.target.closest("[data-edit-form]");if(!form)return;e.preventDefault();const id=form.dataset.editForm,submit=form.querySelector('[type="submit"]');submit.disabled=true;try{const body=Object.fromEntries(new FormData(form));body.price=Number(body.price);await api("/api/listings/"+id,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});notify("محصول به‌روزرسانی شد.");const data=await api("/api/listings");renderProducts((data.items||[]).filter(p=>Number(p.store_id)===Number(store.id)));}catch(err){notify(err.message);submit.disabled=false;}});
    }catch(e){status.textContent="برای بارگذاری پنل، صفحه را تازه‌سازی کن.";}
  }
  async function shareContent(url,title){
    const absolute=new URL(url,location.origin).href;
    const message=(title||"این صفحه")+" در کی‌داره";
    try {
      if(navigator.share){await navigator.share({title:title||"کی‌داره",text:message,url:absolute});return;}
      const wa="https://wa.me/?text="+encodeURIComponent(message+"\\n"+absolute);
      const popup=window.open(wa,"_blank","noopener,noreferrer");
      if(!popup){try{await navigator.clipboard.writeText(absolute);notify("پیوند کپی شد؛ آن را در شبکه اجتماعی دلخواه بفرست.");}catch{notify("پیوند صفحه: "+absolute);}}
    } catch(error){if(error.name!=="AbortError")notify("اشتراک‌گذاری انجام نشد.");}
  }
  document.addEventListener("click",async e=>{const share=e.target.closest("[data-share-url]");if(share){e.preventDefault();e.stopPropagation();await shareContent(share.dataset.shareUrl,share.dataset.shareTitle||"");return;}const b=e.target.closest("[data-save]");if(b){e.preventDefault();b.disabled=true;try{const saved=await saveProduct(b.dataset.save);b.textContent=saved?"♥ ذخیره شد":"♡ ذخیره";}finally{b.disabled=false;}}});
  switch(page.type){case"search":initSearch();break;case"stores":initStores();break;case"store-detail":initStoreDetail();break;case"product-detail":initProductDetail();break;case"saved":initSaved();break;case"following":initFollowing();break;case"account":initAccount();break;case"seller":initSeller();break;}
})();