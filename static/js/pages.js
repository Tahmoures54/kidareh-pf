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
    return '<article class="page-listing-card"><a class="page-listing-art" href="/product/'+item.id+'" aria-label="'+escapeHTML(item.title)+'">'+art+'</a><div class="page-listing-body"><div class="page-listing-meta"><span>'+escapeHTML(item.city)+'</span><span>·</span><span>'+escapeHTML(categoryNames[item.category]||"کالا")+'</span></div><h3>'+escapeHTML(item.title)+'</h3><p>'+escapeHTML(item.description||"برای اطلاعات بیشتر، جزئیات کالا را ببین.")+'</p><div class="page-listing-footer"><strong>'+price+'</strong><a href="/product/'+item.id+'">جزئیات ←</a><button type="button" data-save="'+item.id+'">♡ ذخیره</button></div></div></article>';
  }
  function storeCard(store){
    return '<a class="page-store-card" href="/store/'+store.id+'"><span class="page-store-mark">⌂</span><span class="page-store-copy"><strong>'+escapeHTML(store.name)+'</strong><small>'+escapeHTML(store.city)+' · '+fmt.format(store.product_count||0)+' کالا · '+fmt.format(store.follower_count||0)+' دنبال‌کننده</small><p>'+escapeHTML(store.description||"برای دیدن کالاهای این فروشگاه وارد ویترین شو.")+'</p></span></a>';
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
      document.querySelector("#productDetail").innerHTML='<div class="product-detail-art">'+art+'</div><div class="product-detail-copy"><div class="page-listing-meta">'+escapeHTML(p.city)+' · '+escapeHTML(categoryNames[p.category]||"کالا")+'</div><h2>'+escapeHTML(p.title)+'</h2><strong class="product-detail-price">'+price+'</strong><p>'+escapeHTML(p.description||"توضیحی برای این کالا ثبت نشده است.")+'</p><div class="account-actions"><button id="productSave" class="button button-primary" type="button">♡ ذخیره کالا</button>'+(p.store_id?'<a class="button button-outline" href="/store/'+p.store_id+'">مشاهده فروشگاه</a>':'')+'</div>'+(p.seller_phone?'<p><a class="button button-outline" href="tel:'+escapeHTML(p.seller_phone)+'">تماس با فروشنده</a></p>':'')+'</div>';
      document.querySelector("#productSave").addEventListener("click",()=>saveProduct(p.id));
    }catch(e){document.querySelector("#productDetail").innerHTML='<div class="empty-page-state">این کالا پیدا نشد یا حذف شده است.</div>';}
  }
  async function saveProduct(id){
    const ids=new Set((()=>{try{return JSON.parse(localStorage.getItem(savedKey)||"[]").map(String)}catch{return []}})());
    if(ids.has(String(id)))ids.delete(String(id));else ids.add(String(id));
    localStorage.setItem(savedKey,JSON.stringify([...ids]));notify(ids.has(String(id))?"کالا ذخیره شد.":"کالا از ذخیره‌ها حذف شد.");
  }
  async function initSaved(){
    const target=document.querySelector("#pageListings");let ids=[];
    try{ids=JSON.parse(localStorage.getItem(savedKey)||"[]").map(String)}catch{}
    const items=[];
    for(const id of ids){try{const d=await api("/api/listings/"+encodeURIComponent(id));if(d.item)items.push(d.item)}catch{}}
    target.innerHTML=items.length?items.map(productCard).join(""):'<div class="empty-page-state">هنوز کالایی ذخیره نکرده‌ای. در صفحه جست‌وجو روی «ذخیره» بزن تا اینجا پیدایش کنی.</div>';
    document.querySelector("#savedHint").textContent=items.length?"ذخیره‌های مهمان روی همین مرورگر و دستگاه نگهداری می‌شوند.":"";
    document.querySelector("#clearSaved")?.addEventListener("click",()=>{localStorage.removeItem(savedKey);target.innerHTML='<div class="empty-page-state">فهرست ذخیره‌ها پاک شد.</div>';notify("ذخیره‌ها پاک شدند.")});
  }
  async function initFollowing(){
    const target=document.querySelector("#pageStores");
    try{const me=await api("/api/auth/me");if(!me.user){target.innerHTML='<div class="empty-page-state">برای دیدن فروشگاه‌های دنبال‌شده، <a href="/account">وارد حساب شو</a>. البته دیدن بقیه بازار آزاد است.</div>';return}
      const data=await api("/api/stores/following");target.innerHTML=data.items.length?data.items.map(storeCard).join(""):'<div class="empty-page-state">هنوز فروشگاهی را دنبال نکرده‌ای. از صفحه فروشگاه‌ها شروع کن.</div>';
    }catch(e){target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>'}
  }
  async function initAccount(){
    const status=document.querySelector("#accountStatus"),actions=document.querySelector("#accountActions");
    try{const data=await api("/api/auth/me");if(data.user){status.innerHTML='<strong>سلام '+escapeHTML(data.user.name)+'!</strong><br>شماره همراه: '+escapeHTML(data.user.phone)+'<br>نوع حساب: '+(data.user.role==="seller"?"فروشنده":"خریدار");actions.innerHTML='<a class="button button-primary" href="/seller">مدیریت ویترین</a><a class="button button-outline" href="/saved">محصولات ذخیره‌شده</a><button id="logoutButton" class="button button-outline" type="button">خروج از حساب</button>';document.querySelector("#logoutButton").addEventListener("click",async()=>{try{await api("/api/auth/logout",{method:"POST"});location.reload()}catch(e){notify(e.message)}})}else{status.textContent="هنوز وارد حساب نشده‌ای. برای گشتن در بازار نیازی به حساب نیست.";actions.innerHTML='<a class="button button-primary" href="/?auth=signup">ورود یا ثبت‌نام</a><a class="button button-outline" href="/seller">ساخت ویترین فروشگاه</a>'}}catch(e){status.textContent="وضعیت حساب در دسترس نیست."}
  }
  async function initSeller(){
    const status=document.querySelector("#sellerStatus"),form=document.querySelector("#storeCreateForm");
    try{const me=await api("/api/auth/me");if(!me.user){status.innerHTML='برای مدیریت ویترین، ابتدا <a href="/account">وارد حساب شو</a>. دیدن محصولات و فروشگاه‌ها بدون حساب آزاد است.';return}
      if(me.user.role!=="seller"){status.textContent="حساب شما خریدار است. با ساخت ویترین، حساب به فروشنده تبدیل می‌شود.";form.hidden=false}else{status.textContent="حساب فروشنده فعال است."}
      const storeData=await api("/api/my/store");
      if(storeData.item){status.innerHTML='<strong>'+escapeHTML(storeData.item.name)+'</strong><br>'+escapeHTML(storeData.item.city)+' · ویترین فعال';form.hidden=true;
        const listings=await api("/api/listings");const mine=listings.items.filter(p=>p.store_id===storeData.item.id);const target=document.querySelector("#pageListings");target.innerHTML=mine.length?mine.map(productCard).join(""):'<div class="empty-page-state">ویترین ساخته شده اما هنوز کالایی ندارد.</div>';document.querySelector("#pageResultsCount").textContent=fmt.format(mine.length)+" کالا";
      }else{form.hidden=false}
      form.addEventListener("submit",async e=>{e.preventDefault();try{if(me.user.role!=="seller")await api("/api/auth/become-seller",{method:"POST"});const body=Object.fromEntries(new FormData(form));const created=await api("/api/stores",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});notify("ویترین ساخته شد.");location.href="/store/"+created.item.id}catch(err){notify(err.message)}});
    }catch(e){status.textContent="برای بارگذاری پنل، صفحه را تازه‌سازی کن."}
  }
  document.addEventListener("click",e=>{const b=e.target.closest("[data-save]");if(b){saveProduct(b.dataset.save);b.textContent="♥ ذخیره شد"}});
  switch(page.type){case"search":initSearch();break;case"stores":initStores();break;case"store-detail":initStoreDetail();break;case"product-detail":initProductDetail();break;case"saved":initSaved();break;case"following":initFollowing();break;case"account":initAccount();break;case"seller":initSeller();break;}
})();