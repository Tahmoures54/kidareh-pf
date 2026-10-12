(() => {
  const page = window.KIDAREH_PAGE || {};
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const toast = document.querySelector("#pageToast");
  const fmt = new Intl.NumberFormat("fa-IR");
  const savedKey = "kidareh-saved-products";
  const escapeHTML = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const categoryNames = {home:"خانه و زندگی",digital:"دیجیتال",fashion:"پوشاک",vehicle:"خودرو",services:"خدمات",other:"سایر"};
  function navLinks(lat, lng) {
    if (lat == null || lng == null || lat === "" || lng === "") return null;
    const la = Number(lat), lo = Number(lng);
    if (!Number.isFinite(la) || !Number.isFinite(lo) || la < -90 || la > 90 || lo < -180 || lo > 180) return null;
    const sLat = encodeURIComponent(String(la));
    const sLng = encodeURIComponent(String(lo));
    return {
      neshan: "https://nshn.ir?destination=" + sLat + "," + sLng + "&vehicle=d",
      balad: "https://balad.ir/location?latitude=" + sLat + "&longitude=" + sLng,
      google: "https://www.google.com/maps/dir/?api=1&destination=" + sLat + "," + sLng,
    };
  }
  function navigationSearchLinks(destination) {
    const query = encodeURIComponent(String(destination || "").trim());
    if (!query) return null;
    return {
      neshan: "https://nshn.ir/?destination=" + query,
      balad: "https://balad.ir/search/" + query,
      google: "https://www.google.com/maps/dir/?api=1&destination=" + query,
    };
  }
  function navigateButtonsHTML(lat, lng, opts) {
    const links = navLinks(lat, lng);
    const label = (opts && opts.label) || "مسیریابی به فروشگاه";
    const actions = links || navigationSearchLinks(opts && opts.destination);
    if (!actions) return "";
    return '<div class="nav-to-store" role="group" aria-label="مسیریابی">' +
      '<span class="nav-to-store-label">' + escapeHTML(label) + '</span>' +
      '<div class="nav-to-store-actions">' +
      '<a class="nav-btn nav-btn-neshan" target="_blank" rel="noopener noreferrer" href="' + actions.neshan + '">نشان</a>' +
      '<a class="nav-btn nav-btn-balad" target="_blank" rel="noopener noreferrer" href="' + actions.balad + '">بلد</a>' +
      '<a class="nav-btn nav-btn-google" target="_blank" rel="noopener noreferrer" href="' + actions.google + '">گوگل مپ</a>' +
      '</div>' +
      '<p class="nav-to-store-hint">مسیر در اپ مسیریابی باز می‌شود؛ مقصد بر اساس اطلاعات ثبت‌شده است.</p></div>';
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
  function availabilityHTML(item) {
    const states = {
      in_stock: ["موجود است", "stock-available"],
      out_of_stock: ["فعلاً ناموجود", "stock-unavailable"],
      ask: ["موجودی را تلفنی بپرسید", "stock-confirm"],
    };
    const [label, cls] = states[item.availability_status] || states.ask;
    let freshness = "";
    if (item.price_updated_at) {
      const parsed = new Date(item.price_updated_at);
      if (!Number.isNaN(parsed.getTime())) freshness = "آخرین به‌روزرسانی قیمت: " + parsed.toLocaleDateString("fa-IR");
    }
    const distance = item.distance_km != null ? "حدود " + fmt.format(item.distance_km) + " کیلومتر" : "";
    return '<div class="listing-trust-meta"><span class="' + cls + '">' + label + '</span><small>' +
      escapeHTML([freshness, distance].filter(Boolean).join(" · ")) + '</small></div>';
  }
  function productCard(item){
    const price = Number(item.price)>0 ? fmt.format(item.price)+" تومان" : "قیمت توافقی";
    const art = item.image_path ? '<img src="'+escapeHTML(item.image_path)+'" alt="'+escapeHTML(item.title)+'" loading="lazy">' : '<span>'+escapeHTML(item.emoji||"🛍️")+'</span>';
    const paidTag = item.paid_tag ? '<span class="paid-listing-tag tag-' + escapeHTML(item.paid_tag.type) + '">' + escapeHTML(item.paid_tag.label) + '</span>' : '';
    return '<article class="page-listing-card"><a class="page-listing-art" href="/product/'+item.id+'" aria-label="'+escapeHTML(item.title)+'">'+art+paidTag+'</a><div class="page-listing-body"><div class="page-listing-meta"><span>'+escapeHTML(item.city)+'</span><span>·</span><span>'+escapeHTML(item.category_name||item.category_name||categoryNames[item.category]||"کالا")+'</span></div>'+availabilityHTML(item)+'<h3>'+escapeHTML(item.title)+'</h3><p>'+escapeHTML(item.description||"برای اطلاعات بیشتر، جزئیات کالا را ببین.")+'</p><div class="page-listing-footer"><strong>'+price+'</strong><a href="/product/'+item.id+'">جزئیات ←</a>'+(item.latitude!=null&&item.longitude!=null?'<a class="nav-btn nav-btn-compact" target="_blank" rel="noopener noreferrer" href="https://nshn.ir?destination='+encodeURIComponent(item.latitude)+','+encodeURIComponent(item.longitude)+'&vehicle=d" title="مسیریابی با نشان">مسیریابی</a>':'')+'<button type="button" data-save="'+item.id+'">♡ ذخیره</button><button class="share-button" type="button" data-share-url="/product/'+item.id+'" data-share-title="کالای '+escapeHTML(item.title)+'" aria-label="اشتراک‌گذاری کالا" title="اشتراک‌گذاری کالا">↗</button><button type="button" data-report-listing="'+item.id+'">گزارش</button></div></div></article>';
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
    if(!append){ state.items=[]; state.cursor=null; state.hasMore=false; target.innerHTML='<div class="loading-card">در حال دریافت کالاها…</div>'; }
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
      if (!append && !state.items.length && typeof options.onEmpty === "function") options.onEmpty({ params, target });
      const count=document.querySelector("#pageResultsCount");if(count)count.textContent=fmt.format(state.items.length)+" کالا";
      let more=document.querySelector("#pageLoadMoreListings");
      if(!more){ more=document.createElement("button"); more.id="pageLoadMoreListings"; more.type="button"; more.className="button button-outline"; more.style.margin="1rem auto"; more.textContent="نمایش کالاهای بیشتر"; target.insertAdjacentElement("afterend", more); more.addEventListener("click",()=>loadListings(container, params, {append:true})); }
      more.style.display=state.hasMore?"block":"none";
    } catch(e){if(!append) target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>';}
  }
  async function loadStores(container, query="", options={}) {
    const target=document.querySelector(container);if(!target)return;
    const city=String(options.city||"").trim();
    const append=Boolean(options.append);
    const stateKey=container+"|stores";
    window.__kidarehPageState=window.__kidarehPageState||{};
    const state=window.__kidarehPageState[stateKey]||{items:[],cursor:null,hasMore:false};
    if(!append){ state.items=[]; state.cursor=null; state.hasMore=false; target.innerHTML='<div class="loading-card">در حال دریافت فروشگاه‌ها…</div>'; }
    try {
      const qs=new URLSearchParams();
      if(query) qs.set("q",query);
      if(city) qs.set("city",city);
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
      if(!more){ more=document.createElement("button"); more.id="pageLoadMoreStores"; more.type="button"; more.className="button button-outline"; more.style.margin="1rem auto"; more.textContent="نمایش فروشگاه‌های بیشتر"; target.insertAdjacentElement("afterend", more); }
      more.onclick=()=>loadStores(container, query, {append:true, city});
      more.style.display=state.hasMore?"block":"none";
    }catch(e){if(!append) target.innerHTML='<div class="empty-page-state">'+escapeHTML(e.message)+'</div>';}
  }
  async function initStores(){
    const target=document.querySelector("#pageStores");
    const form=document.querySelector("#storeSearchForm");
    const queryInput=document.querySelector("#storeQuery");
    const cityInput=document.querySelector("#storeCity");
    if(!target || !form || !queryInput || !cityInput) return;
    const run=()=>loadStores("#pageStores", queryInput.value.trim(), {city: cityInput.value.trim()});
    form.addEventListener("submit", event=>{event.preventDefault();run();});
    queryInput.addEventListener("search", run);
    cityInput.addEventListener("change", run);
    await run();
  }
  async function initSearch(){
    const form = document.querySelector("#pageSearchForm");
    const queryInput = document.querySelector("#pageQuery");
    const categoryInput = document.querySelector("#pageCategory");
    const availabilityInput = document.querySelector("#pageAvailability");
    const cityInput = document.querySelector("#pageCity");
    const target = document.querySelector("#pageListings");
    if (!form || !queryInput || !categoryInput || !cityInput || !target) return;

    const normalize = value => String(value || "").trim().replace(/[ي]/g, "ی").replace(/[ك]/g, "ک");
    const paramsAtLoad = new URLSearchParams(window.location.search);
    if (availabilityInput) availabilityInput.value = paramsAtLoad.get("availability") || "";
    try {
      if (!paramsAtLoad.has("city")) {
        const savedCity = localStorage.getItem("kidareh.marketCity") || "";
        if (savedCity) cityInput.value = savedCity;
      }
    } catch (_) { /* Search remains available if browser storage is blocked. */ }

    let cityProvince = paramsAtLoad.get("province") || "";
    let scope = paramsAtLoad.get("scope") === "country" ? "country" : (cityProvince ? "province" : "city");
    let requestSerial = 0;
    let nearbyCoords = null;
    const nearbyButton = document.querySelector("#pageNearbySearchButton");
    const nearbyRadius = document.querySelector("#pageNearbyRadius");
    const selectedRadius = () => {
      const value = Number(nearbyRadius?.value || 10);
      return [3, 5, 10, 25, 50].includes(value) ? value : 10;
    };

    async function resolveProvince() {
      if (!cityInput.value.trim()) return "";
      try {
        const response = await fetch("/api/locations?q=" + encodeURIComponent(cityInput.value.trim()), {
          credentials: "same-origin",
          headers: { "Accept": "application/json" }
        });
        if (!response.ok) return "";
        const data = await response.json();
        const city = (data.items || []).find(item =>
          item.type === "city" && normalize(item.name) === normalize(cityInput.value)
        );
        return city?.province || "";
      } catch (_) { return ""; }
    }

    function currentParams() {
      const params = { q: queryInput.value.trim(), category: categoryInput.value };
      if (availabilityInput?.value) params.availability = availabilityInput.value;
      if (nearbyCoords) {
        params.lat = String(nearbyCoords.lat);
        params.lon = String(nearbyCoords.lon);
        params.radius_km = String(selectedRadius());
      } else if (scope === "city" && cityInput.value.trim()) {
        params.city = cityInput.value.trim();
      } else if (scope === "province" && cityProvince) {
        params.province = cityProvince;
      }
      return params;
    }

    function syncUrl() {
      const params = new URLSearchParams();
      if (queryInput.value.trim()) params.set("q", queryInput.value.trim());
      if (categoryInput.value) params.set("category", categoryInput.value);
      if (availabilityInput?.value) params.set("availability", availabilityInput.value);
      if (cityInput.value.trim()) params.set("city", cityInput.value.trim());
      if (scope === "province" && cityProvince) params.set("province", cityProvince);
      if (scope === "country") params.set("scope", "country");
      window.history.pushState({ search: true }, "", "/search" + (params.size ? "?" + params.toString() : ""));
    }

    function showEmptyOptions({ target: resultTarget }) {
      const message = document.createElement("div");
      message.className = "search-expansion";
      const title = document.createElement("strong");
      const description = document.createElement("p");
      const actions = document.createElement("div");
      actions.className = "search-expansion-actions";
      if (scope === "city") {
        title.textContent = "در این شهر نتیجه‌ای پیدا نشد";
        description.textContent = cityProvince
          ? "می‌خواهی همین عبارت را در کل استان " + cityProvince + " جست‌وجو کنیم؟"
          : "می‌توانیم جست‌وجو را در سراسر کشور گسترش بدهیم.";
        if (cityProvince) {
          const provinceButton = document.createElement("button");
          provinceButton.type = "button";
          provinceButton.className = "button button-primary";
          provinceButton.dataset.searchScope = "province";
          provinceButton.textContent = "جست‌وجو در استان " + cityProvince;
          actions.appendChild(provinceButton);
        }
        const countryButton = document.createElement("button");
        countryButton.type = "button";
        countryButton.className = "button button-outline";
        countryButton.dataset.searchScope = "country";
        countryButton.textContent = "جست‌وجو در سراسر کشور";
        actions.appendChild(countryButton);
      } else if (scope === "province") {
        title.textContent = "در استان " + cityProvince + " نتیجه‌ای پیدا نشد";
        description.textContent = "اگر مایل باشی، همین جست‌وجو را در سراسر کشور ادامه می‌دهیم.";
        const countryButton = document.createElement("button");
        countryButton.type = "button";
        countryButton.className = "button button-primary";
        countryButton.dataset.searchScope = "country";
        countryButton.textContent = "جست‌وجو در سراسر کشور";
        actions.appendChild(countryButton);
      } else {
        title.textContent = "نتیجه‌ای پیدا نشد";
        description.textContent = "عبارت جست‌وجو یا دسته‌بندی را تغییر بده و دوباره امتحان کن.";
      }
      message.append(title, description, actions);
      resultTarget.replaceChildren(message);
    }

    async function run(nextScope = scope, updateHistory = false) {
      const serial = ++requestSerial;
      scope = nextScope;
      if (scope === "province" && !cityProvince) cityProvince = await resolveProvince();
      if (scope === "province" && !cityProvince) scope = "country";
      const params = currentParams();
      if (updateHistory) syncUrl();
      await loadListings("#pageListings", params, {
        onEmpty: ({ target: resultTarget }) => {
          if (serial === requestSerial) showEmptyOptions({ target: resultTarget });
        }
      });
    }

    form.addEventListener("submit", async event => {
      event.preventDefault();
      nearbyCoords = null;
      cityProvince = await resolveProvince();
      run("city", true);
    });
    target.addEventListener("click", event => {
      const button = event.target.closest("[data-search-scope]");
      if (!button) return;
      event.preventDefault();
      run(button.dataset.searchScope, true);
    });
    window.addEventListener("popstate", async () => {
      const params = new URLSearchParams(window.location.search);
      queryInput.value = params.get("q") || "";
      categoryInput.value = params.get("category") || "";
      if (availabilityInput) availabilityInput.value = params.get("availability") || "";
      cityInput.value = params.get("city") || cityInput.value;
      cityProvince = params.get("province") || "";
      const nextScope = params.get("scope") === "country" ? "country" : (cityProvince ? "province" : "city");
      if (nextScope === "city") cityProvince = await resolveProvince();
      run(nextScope);
    });
    availabilityInput?.addEventListener("change", () => run(scope, true));

    cityInput.addEventListener("change", () => {
      cityProvince = "";
      scope = "city";
      nearbyCoords = null;
      try {
        if (cityInput.value.trim()) localStorage.setItem("kidareh.marketCity", cityInput.value.trim());
        else localStorage.removeItem("kidareh.marketCity");
      } catch (_) { /* Manual city selection still works without storage. */ }
      run("city", true);
    });

    nearbyRadius?.addEventListener("change", () => {
      if (nearbyCoords) run(scope, false);
    });

    nearbyButton?.addEventListener("click", () => {
      if (!navigator.geolocation) {
        nearbyButton.textContent = "مکان‌یابی در این مرورگر پشتیبانی نمی‌شود";
        return;
      }
      const originalLabel = "⌖ یافتن کالاهای اطراف من";
      nearbyButton.disabled = true;
      nearbyButton.textContent = "در حال دریافت موقعیت…";
      navigator.geolocation.getCurrentPosition(
        position => {
          nearbyCoords = { lat: position.coords.latitude, lon: position.coords.longitude };
          nearbyButton.disabled = false;
          nearbyButton.textContent = "کالاهای اطراف من ✓";
          run(scope, false);
        },
        () => {
          nearbyButton.disabled = false;
          nearbyButton.textContent = originalLabel;
          notify("موقعیت دریافت نشد؛ اجازهٔ مکان‌یابی را بررسی کن یا شهر را انتخاب کن.");
        },
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
      );
    });
    if (scope === "city") cityProvince = await resolveProvince();
    await run(scope);
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
        const destination = [s.name, s.address, s.city].filter(Boolean).join("، ");
        if (s.latitude != null && s.longitude != null) {
          navHost.innerHTML = navigateButtonsHTML(s.latitude, s.longitude, {label: "مسیریابی به «" + (s.name || "فروشگاه") + "»"});
        } else if (destination) {
          navHost.innerHTML = navigateButtonsHTML(null, null, {label: "جست‌وجوی مسیر بر اساس آدرس", destination}) +
            (s.address ? '<div class="nav-to-store-address"><p class="nav-address-text">' + escapeHTML(s.address) + '</p><button type="button" class="button button-outline" id="copyStoreAddress">کپی آدرس</button></div>' : '');
          document.querySelector("#copyStoreAddress")?.addEventListener("click", async () => { try { await navigator.clipboard.writeText(s.address); notify("آدرس کپی شد."); } catch { notify("کپی پشتیبانی نشد."); } });
        } else navHost.innerHTML = "";
      }
      const shareStore=document.querySelector("#shareStore");if(shareStore){shareStore.dataset.shareUrl="/store/"+s.id;shareStore.dataset.shareTitle="ویترین "+s.name;}
      const follow=document.querySelector("#followStore");follow.textContent=data.following?"✓ دنبال می‌کنی":"♡ دنبال‌کردن فروشگاه";
      follow.addEventListener("click",async()=>{try{const me=await api("/api/auth/me");if(!me.user){notify("برای دنبال‌کردن فروشگاه ابتدا وارد حساب شو.");location.href="/login";return;}const result=await api("/api/stores/"+page.storeId+"/follow",{method:"POST"});follow.textContent=result.following?"✓ دنبال می‌کنی":"♡ دنبال‌کردن فروشگاه";document.querySelector("#storeMeta").textContent=s.city+" · "+fmt.format(s.product_count||0)+" کالا · "+fmt.format(result.follower_count||0)+" دنبال‌کننده";notify(result.following?"فروشگاه به دنبال‌شده‌ها اضافه شد.":"فروشگاه از دنبال‌شده‌ها برداشته شد.");}catch(e){notify(e.message)}});
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
      document.querySelector("#productDetail").innerHTML='<div class="product-detail-art">'+art+'</div><div class="product-detail-copy"><div class="page-listing-meta">'+escapeHTML(p.city)+' · '+escapeHTML(p.category_name||p.category_name||categoryNames[p.category]||"کالا") + '</div>'+availabilityHTML(p)+'<div>' + paidTag + '</div><h2>'+escapeHTML(p.title)+'</h2><strong class="product-detail-price">'+price+'</strong><p>'+escapeHTML(p.description||"توضیحی برای این کالا ثبت نشده است.")+'</p><div class="account-actions"><button id="productSave" class="button button-primary" type="button">♡ ذخیره کالا</button><button class="share-button" type="button" data-share-url="/product/'+p.id+'" data-share-title="کالای '+escapeHTML(p.title)+'">↗ اشتراک‌گذاری کالا</button>'+(p.store_id?'<a class="button button-outline" href="/store/'+p.store_id+'">مشاهده فروشگاه</a>':'')+'</div>'+(p.seller_phone?'<p><a class="button button-outline" href="tel:'+escapeHTML(p.seller_phone)+'">تماس با فروشنده</a></p>':'')+navBlock+'</div>';
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
    notify(set.has(key)?"کالا به ذخیره‌ها اضافه شد ♡":"کالا از ذخیره‌ها برداشته شد.");if(page.type==="saved")await initSaved();return set.has(key);
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
    const form=document.querySelector("#profileEditForm"),nameInput=document.querySelector("#profileName"),phoneInput=document.querySelector("#profilePhone"),feedback=document.querySelector("#profileFeedback");
    let user=null;
    const showFeedback=(message,error=false)=>{if(feedback){feedback.textContent=message;feedback.style.color=error?"#B91C1C":"#0E7490";}};
    try{
      const data=await api("/api/auth/me");user=data.user;
      if(user){
        if(status)status.innerHTML='<strong>سلام '+escapeHTML(user.name||"")+'!</strong><p>پروفایل شما آماده است.</p>';
        if(actions)actions.innerHTML='<button id="editProfileButton" class="button button-primary" type="button">ویرایش پروفایل</button><a class="button button-outline" href="'+(user.role==="seller"?"/seller":"/search")+'">'+(user.role==="seller"?"رفتن به داشبورد فروشنده":"شروع جست‌وجو")+'</a><button id="logoutButton" class="button button-outline" type="button">خروج</button>';
        if(form){form.hidden=true;nameInput.value=user.name||"";phoneInput.value=user.phone||"";}
        document.querySelector("#editProfileButton")?.addEventListener("click",()=>{form.hidden=false;nameInput.value=user.name||"";nameInput.focus();});
        document.querySelector("#cancelProfileButton")?.addEventListener("click",()=>{form.hidden=true;nameInput.value=user.name||"";showFeedback("");});
        form?.addEventListener("submit",async(event)=>{event.preventDefault();const button=document.querySelector("#saveProfileButton");button.disabled=true;try{const updated=await api("/api/auth/profile",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:nameInput.value.trim()})});user=updated.user;status.innerHTML='<strong>سلام '+escapeHTML(user.name)+'!</strong><p>پروفایل با موفقیت ذخیره شد.</p>';form.hidden=true;showFeedback("تغییرات ذخیره شد.");}catch(e){showFeedback(e.message||"ذخیره اطلاعات انجام نشد.",true);}finally{button.disabled=false;}});
        document.querySelector("#logoutButton")?.addEventListener("click",async()=>{try{await api("/api/auth/logout",{method:"POST"});location.assign("/");}catch(e){notify(e.message);}});
      }else{
        if(status)status.textContent="برای ساخت پروفایل شخصی، فقط شماره همراهت را تأیید کن.";
        if(actions)actions.innerHTML='<a class="button button-primary" href="/register">ثبت‌نام سریع</a><a class="button button-outline" href="/login">ورود</a>';
      }
    }catch(e){if(status)status.textContent="وضعیت حساب در دسترس نیست؛ صفحه را تازه‌سازی کنید.";}
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
