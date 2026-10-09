(() => {
  const page = window.KIDAREH_PAGE || {};
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const toast = document.querySelector("#pageToast");
  const fmt = new Intl.NumberFormat("fa-IR");
  const savedKey = "kidareh-saved-products";
  const escapeHTML = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const categoryNames = {home:"خانه و زندگی",digital:"دیجیتال",fashion:"پوشاک",vehicle:"خودرو",services:"خدمات",other:"سایر"};
  /** Deep-links to Iranian + Google navigation apps — we do not build a router. */
  function navLinks(lat, lng) {
    const la = Number(lat), lo = Number(lng);
    if (!Number.isFinite(la) || !Number.isFinite(lo)) return null;
    const sLat = encodeURIComponent(String(la));
    const sLng = encodeURIComponent(String(lo));
    return {
      neshan: "https://nshn.ir?destination=" + sLat + "," + sLng + "&vehicle=d",
      balad: "https://balad.ir/location?latitude=" + sLat + "&longitude=" + sLng,
      google: "https://www.google.com/maps/dir/?api=1&destination=" + sLat + "," + sLng,
    };
  }
  function navigateButtonsHTML(lat, lng, opts) {
    const links = navLinks(lat, lng);
    if (!links) return "";
    const label = (opts && opts.label) || "مسیریابی به فروشگاه";
    return '<div class="nav-to-store" role="group" aria-label="مسیریابی">' +
      '<span class="nav-to-store-label">' + escapeHTML(label) + '</span>' +
      '<div class="nav-to-store-actions">' +
      '<a class="nav-btn nav-btn-neshan" target="_blank" rel="noopener noreferrer" href="' + links.neshan + '">نشان</a>' +
      '<a class="nav-btn nav-btn-balad" target="_blank" rel="noopener noreferrer" href="' + links.balad + '">بلد</a>' +
      '<a class="nav-btn nav-btn-google" target="_blank" rel="noopener noreferrer" href="' + links.google + '">گوگل مپ</a>' +
      '</div>' +
      '<p class="nav-to-store-hint">مسیر در اپ مسیریابی باز می‌شود.</p></div>';
  }
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
    const paidTag = item.paid_tag ? '<span class="paid-listing-tag tag-' + escapeHTML(item.paid_tag.type) + '">' + escapeHTML(item.paid_tag.label) + '</span>' : '';
    return '<article class="page-listing-card"><a class="page-listing-art" href="/product/'+item.id+'" aria-label="'+escapeHTML(item.title)+'">'+art+paidTag+'</a><div class="page-listing-body"><div class="page-listing-meta"><span>'+escapeHTML(item.city)+'</span><span>·</span><span>'+escapeHTML(categoryNames[item.category]||"کالا")+'</span></div><h3>'+escapeHTML(item.title)+'</h3><p>'+escapeHTML(item.description||"برای اطلاعات بیشتر، جزئیات کالا را ببین.")+'</p><div class="page-listing-footer"><strong>'+price+'</strong><a href="/product/'+item.id+'">جزئیات ←</a>'+(item.latitude!=null&&item.longitude!=null?'<a class="nav-btn nav-btn-compact" target="_blank" rel="noopener noreferrer" href="https://nshn.ir?destination='+encodeURIComponent(item.latitude)+','+encodeURIComponent(item.longitude)+'&vehicle=d" title="مسیریابی با نشان">مسیریابی</a>':'')+'<button type="button" data-save="'+item.id+'">♡ ذخیره</button><button class="share-button" type="button" data-share-url="/product/'+item.id+'" data-share-title="کالای '+escapeHTML(item.title)+'" aria-label="اشتراک‌گذاری کالا" title="اشتراک‌گذاری کالا">↗</button><button type="button" data-report-listing="'+item.id+'">گزارش</button></div></div></article>';
  }
  function storeCard(store){
    const badge = store.blue_tick_active ? '<span class="store-paid-badge" title="نشان تبلیغاتی زمان‌دار؛ نه تأیید هویت">✓ تیک آبی</span>' : '';
    return '<article class="page-store-card"><a class="page-store-card-link" href="/store/'+store.id+'"><span class="page-store-mark">⌂</span><span class="page-store-copy"><strong>'+escapeHTML(store.name)+' '+badge+'</strong><small>'+escapeHTML(store.city)+' · '+fmt.format(store.product_count||0)+' کالا · '+fmt.format(store.follower_count||0)+' دنبال‌کننده</small><p>'+escapeHTML(store.description||"برای دیدن کالاهای این فروشگاه وارد ویترین شو.")+'</p></span></a><button class="share-button" type="button" data-share-url="/store/'+store.id+'" data-share-title="ویترین '+escapeHTML(store.name)+'" aria-label="اشتراک‌گذاری ویترین" title="اشتراک‌گذاری ویترین">↗ معرفی ویترین</button></article>';
  }
  async function loadListings(container, params={}, options={}) {
    const target=document.querySelector(container); if(!target)return;
    const append=Boolean(options.append);
    const stateKey=container+"|listings";
    window.__kidarehPageState=window.__kidarehPageState||{};
    const state=window.__kidarehPageState[stateKey]||{items:[],cursor:null,hasMore:false};
    if(!append){
      state.items=[]; state.cursor=null; state.hasMore=false;
      target.innerHTML='<div class="loading-card">در حال دریافت کالاها…</div>';
    }
    try {
      const qs=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>{if(v)qs.set(k,v)});
      qs.set("limit", params.limit||"50");
      if(append && state.cursor) qs.set("before_id", String(state.cursor));
      const data=await api("/api/listings?"+qs.toString());
      const items=data.items||[];
      state.items=append?state.items.concat(items):items;
      state.hasMore=Boolean(data.has_more);
      state.cursor=data.next_before_id||(items.length?items[items.length-1].id:null);
      window.__kidarehPageState[stateKey]=state;
      target.innerHTML=state.items.length?state.items.map(productCard).join(""):'<div class="empty-page-state">کالایی با این مشخصات پیدا نشد. عبارت یا فیلتر دیگری را امتحان کن.</div>';
      const count=document.querySelector("#pageResultsCount");if(count)count.textContent=fmt.format(state.items.length)+" کالا";
      let more=document.querySelector("#pageLoadMoreListings");
      if(!more){
        more=document.createElement("button");
        more.id="pageLoadMoreListings";
        more.type="button";
        more.className="button button-outline";
        more.style.margin="1rem auto";
        more.textContent="نمایش کالاهای بیشتر";
        target.insertAdjacentElement("afterend", more);
        more.addEventListener("click",()=>loadListings(container, params, {append:true}));
      }
      more.style.display=state.hasMore?"block":"none";
    } catch(e){if(!append) target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>';}
  }
  async function loadStores(container, query="", options={}) {
    const target=document.querySelector(container);if(!target)return;
    const append=Boolean(options.append);
    const stateKey=container+"|stores";
    window.__kidarehPageState=window.__kidarehPageState||{};
    const state=window.__kidarehPageState[stateKey]||{items:[],cursor:null,hasMore:false};
    if(!append){
      state.items=[]; state.cursor=null; state.hasMore=false;
      target.innerHTML='<div class="loading-card">در حال دریافت فروشگاه‌ها…</div>';
    }
    try {
      const qs=new URLSearchParams(query?{q:query}:{});
      qs.set("limit","50");
      if(append && state.cursor) qs.set("before_id", String(state.cursor));
      const data=await api("/api/stores?"+qs.toString());
      const items=data.items||[];
      state.items=append?state.items.concat(items):items;
      state.hasMore=Boolean(data.has_more);
      state.cursor=data.next_before_id||(items.length?items[items.length-1].id:null);
      window.__kidarehPageState[stateKey]=state;
      target.innerHTML=state.items.length?state.items.map(storeCard).join(""):'<div class="empty-page-state">فروشگاهی پیدا نشد. نام دیگری جست‌وجو کن.</div>';
      const count=document.querySelector("#pageResultsCount");if(count)count.textContent=fmt.format(state.items.length)+" فروشگاه";
      let more=document.querySelector("#pageLoadMoreStores");
      if(!more){
        more=document.createElement("button");
        more.id="pageLoadMoreStores";
        more.type="button";
        more.className="button button-outline";
        more.style.margin="1rem auto";
        more.textContent="نمایش فروشگاه‌های بیشتر";
        target.insertAdjacentElement("afterend", more);
        more.addEventListener("click",()=>loadStores(container, query, {append:true}));
      }
      more.style.display=state.hasMore?"block":"none";
    }catch(e){if(!append) target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>';}
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
      document.querySelector("#storeTitle").innerHTML=escapeHTML(s.name)+(s.blue_tick_active?' <span class="store-paid-badge" title="نشان تبلیغاتی زمان‌دار؛ نه تأیید هویت">✓ تیک آبی</span>':'');
      document.querySelector("#storeDescription").textContent=s.description||"به ویترین این فروشگاه خوش آمدید.";
      document.querySelector("#storeMeta").textContent=s.city+" · "+fmt.format(s.product_count||0)+" کالا · "+fmt.format(s.follower_count||0)+" دنبال‌کننده";
      const contact = document.querySelector("#storeContactDetails");
      const details = [];
      if (s.category) details.push("<p><strong>حوزه فعالیت:</strong> "+escapeHTML(s.category)+"</p>");
      if (s.in_person && s.address) details.push("<p><strong>نشانی مراجعه حضوری:</strong> "+escapeHTML(s.address)+"</p>");
      if (s.hours) details.push("<p><strong>ساعات کاری:</strong> "+escapeHTML(s.hours)+"</p>");
      if (s.contact_name) details.push("<p><strong>مسئول پاسخ‌گو:</strong> "+escapeHTML(s.contact_name)+"</p>");
      if (contact) contact.innerHTML = details.join("");
      const navHost = document.querySelector("#storeNavigate");
      if (navHost) {
        if (s.latitude != null && s.longitude != null) {
          navHost.innerHTML = navigateButtonsHTML(s.latitude, s.longitude, {label: "مسیریابی به «" + (s.name || "فروشگاه") + "»"});
        } else if (s.address) {
          navHost.innerHTML = '<div class="nav-to-store nav-to-store-address"><span class="nav-to-store-label">آدرس فروشگاه</span><p class="nav-address-text">' + escapeHTML(s.address) + '</p><button type="button" class="button button-outline" id="copyStoreAddress">کپی آدرس</button><p class="nav-to-store-hint">مختصات ثبت نشده؛ فروشنده می‌تواند در ویترین مختصات را اضافه کند.</p></div>';
          document.querySelector("#copyStoreAddress")?.addEventListener("click", async () => {
            try { await navigator.clipboard.writeText(s.address); notify("آدرس کپی شد."); } catch { notify("کپی پشتیبانی نشد."); }
          });
        } else {
          navHost.innerHTML = "";
        }
      }
      const shareStore=document.querySelector("#shareStore");if(shareStore){shareStore.dataset.shareUrl="/store/"+s.id;shareStore.dataset.shareTitle="ویترین "+s.name;}
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
      const paidTag = p.paid_tag ? '<span class="paid-listing-tag tag-' + escapeHTML(p.paid_tag.type) + '">' + escapeHTML(p.paid_tag.label) + '</span> ' : '';
      const navBlock = navigateButtonsHTML(p.latitude, p.longitude, {label: "مسیریابی به محل کالا / فروشگاه"});
      document.querySelector("#productDetail").innerHTML='<div class="product-detail-art">'+art+'</div><div class="product-detail-copy"><div class="page-listing-meta">'+escapeHTML(p.city)+' · '+escapeHTML(categoryNames[p.category]||"کالا") + '</div><div>' + paidTag + '</div><h2>'+escapeHTML(p.title)+'</h2><strong class="product-detail-price">'+price+'</strong><p>'+escapeHTML(p.description||"توضیحی برای این کالا ثبت نشده است.")+'</p><div class="account-actions"><button id="productSave" class="button button-primary" type="button">♡ ذخیره کالا</button><button class="share-button" type="button" data-share-url="/product/'+p.id+'" data-share-title="کالای '+escapeHTML(p.title)+'">↗ اشتراک‌گذاری کالا</button>'+(p.store_id?'<a class="button button-outline" href="/store/'+p.store_id+'">مشاهده فروشگاه</a>':'')+'</div>'+(p.seller_phone?'<p><a class="button button-outline" href="tel:'+escapeHTML(p.seller_phone)+'">تماس با فروشنده</a></p>':'')+navBlock+'</div>';
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
    target.innerHTML=items.length?items.map(productCard).join(""):'<div class="empty-page-state">هنوز کالایی ذخیره نکرده‌ای.</div>';
  }
  async function initFollowing(){
    const target=document.querySelector("#pageStores");if(!target)return;
    try{const me=await api("/api/auth/me");if(!me.user){target.innerHTML='<div class="empty-page-state">برای دیدن فروشگاه‌های دنبال‌شده وارد حساب شو.</div>';return}
      const data=await api("/api/stores/following");
      target.innerHTML=data.items.length?data.items.map(s=>'<div class="following-store-row">'+storeCard(s)+'</div>').join(""):'<div class="empty-page-state">هنوز فروشگاهی را دنبال نکرده‌ای.</div>';
    }catch(e){target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>'}
  }
  async function initAccount(){
    const status=document.querySelector("#accountStatus"),actions=document.querySelector("#accountActions");
    try{const data=await api("/api/auth/me");if(data.user){status.innerHTML='<strong>سلام '+escapeHTML(data.user.name)+'!</strong><br>شماره: '+escapeHTML(data.user.phone);actions.innerHTML='<a class="button button-primary" href="/seller">مدیریت ویترین</a><button id="logoutButton" class="button button-outline" type="button">خروج</button>';document.querySelector("#logoutButton")?.addEventListener("click",async()=>{await api("/api/auth/logout",{method:"POST"});location.reload();});}else{status.textContent="وارد حساب نشده‌ای.";actions.innerHTML='<a class="button button-primary" href="/?auth=signup">ورود یا ثبت‌نام</a>';}}catch(e){if(status)status.textContent="وضعیت حساب در دسترس نیست.";}
  }
  document.addEventListener("click", async (e) => {
    const saveBtn = e.target.closest("[data-save]");
    if (saveBtn) { e.preventDefault(); await saveProduct(saveBtn.dataset.save); }
  });
  const boot = {
    search: initSearch,
    stores: initStores,
    store: initStoreDetail,
    "store-detail": initStoreDetail,
    product: initProductDetail,
    "product-detail": initProductDetail,
    saved: initSaved,
    following: initFollowing,
    account: initAccount,
  };
  const runner = boot[page.type];
  if (runner) runner();
})();
