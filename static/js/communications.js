(() => {
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const fmt = new Intl.NumberFormat("fa-IR");
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const toast = (message) => { const el=document.querySelector("#pageToast"); if(el){el.textContent=message;el.classList.add("visible");window.setTimeout(()=>el.classList.remove("visible"),2800);} };
  async function api(url, options={}) {
    const headers={Accept:"application/json",...(options.headers||{})};
    if(options.method && options.method!=="GET") headers["X-CSRF-Token"]=token;
    if(options.body) headers["Content-Type"]="application/json";
    const response=await fetch(url,{...options,headers});
    const data=await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(data.message||data.error||"درخواست انجام نشد.");
    return data;
  }
  const date = value => value ? esc(new Date(value.replace(" ","T")+"Z").toLocaleString("fa-IR",{dateStyle:"short",timeStyle:"short"})) : "";
  async function initMessages(){
    const list=document.querySelector("#conversationList"); if(!list)return;
    let active=null;
    const messageBox=document.querySelector("#conversationMessages"),heading=document.querySelector("#conversationHeading"),form=document.querySelector("#messageForm");
    async function openThread(id,title){
      active=id; heading.innerHTML='<h2>'+esc(title)+'</h2><p class="muted">گفت‌وگوی امن درباره همین کالا</p>';
      form.hidden=false; await loadMessages();
    }
    async function loadMessages(){
      if(!active)return;
      try{
        const data=await api("/api/conversations/"+active+"/messages");
        messageBox.innerHTML=data.items.map(m=>'<article class="chat-bubble '+(Number(m.sender_id)===window.KIDAREH_USER_ID?'mine':'')+'"><strong>'+esc(m.sender_name)+'</strong><p>'+esc(m.body)+'</p><small>'+date(m.created_at)+'</small></article>').join("")||'<p class="muted">هنوز پیامی ردوبدل نشده است.</p>';
        messageBox.scrollTop=messageBox.scrollHeight;
      }catch(e){messageBox.innerHTML='<p class="error-text">'+esc(e.message)+'</p>';}
    }
    try{
      const me=await api("/api/auth/me"); window.KIDAREH_USER_ID=me.user?.id;
      const data=await api("/api/conversations");
      list.innerHTML=data.items.map(c=>'<button class="community-list-item" type="button" data-thread="'+c.id+'" data-title="'+esc(c.listing_title)+'"><strong>'+esc(c.listing_title)+'</strong><span>'+esc(c.other_name||"کاربر")+'</span><small>'+esc(c.last_message||"شروع گفت‌وگو")+'</small></button>').join("")||'<p class="muted">هنوز گفت‌وگویی نداری. از صفحه یک کالای فروشنده ثبت‌شده، گزینه گفت‌وگو را بزن.</p>';
      list.querySelectorAll("[data-thread]").forEach(b=>b.addEventListener("click",()=>openThread(Number(b.dataset.thread),b.dataset.title)));
    }catch(e){list.innerHTML='<p class="error-text">'+esc(e.message)+'</p>';}
    form?.addEventListener("submit",async e=>{e.preventDefault();const field=document.querySelector("#messageBody");const body=field.value.trim();if(!body||!active)return;try{await api("/api/conversations/"+active+"/messages",{method:"POST",body:JSON.stringify({body})});field.value="";await loadMessages();}catch(err){toast(err.message);}});
  }
  async function initSupport(){
    const list=document.querySelector("#ticketList");if(!list)return;
    const detail=document.querySelector("#ticketDetail");
    async function openTicket(id){
      try{
        const d=await api("/api/support/tickets/"+id);
        detail.innerHTML='<h3>تیکت #'+fmt.format(id)+' · '+esc(d.ticket.title)+'</h3><div class="ticket-thread">'+d.items.map(m=>'<article class="chat-bubble '+(m.is_admin_reply?'admin-reply':'')+'"><strong>'+esc(m.sender_name)+(m.is_admin_reply?' · پشتیبانی':'')+'</strong><p>'+esc(m.body)+'</p><small>'+date(m.created_at)+'</small></article>').join("")+'</div>'+(d.ticket.status!=="closed"?'<form id="ticketReplyForm" class="stack-form"><label for="ticketReply">پاسخ شما</label><textarea id="ticketReply" rows="3" required maxlength="4000"></textarea><button class="button button-primary" type="submit">ارسال پاسخ</button></form>':'<p class="muted">این تیکت بسته شده است.</p>');
        document.querySelector("#ticketReplyForm")?.addEventListener("submit",async e=>{e.preventDefault();const body=document.querySelector("#ticketReply").value.trim();try{await api("/api/support/tickets/"+id+"/messages",{method:"POST",body:JSON.stringify({body})});await openTicket(id);await loadTickets();}catch(err){toast(err.message);}});
      }catch(e){detail.innerHTML='<p class="error-text">'+esc(e.message)+'</p>';}
    }
    async function loadTickets(){
      try{const data=await api("/api/support/tickets");list.innerHTML=data.items.map(t=>'<button class="community-list-item" type="button" data-ticket="'+t.id+'"><strong>'+esc(t.title)+'</strong><span class="status-pill status-'+esc(t.status)+'">'+({open:"باز",in_progress:"در حال بررسی",answered:"پاسخ داده شد",closed:"بسته"}[t.status]||esc(t.status))+'</span><small>'+esc(t.last_message||"")+'</small></button>').join("")||'<p class="muted">هنوز تیکتی ثبت نکرده‌ای.</p>';list.querySelectorAll("[data-ticket]").forEach(b=>b.addEventListener("click",()=>openTicket(Number(b.dataset.ticket))));}
      catch(e){list.innerHTML='<p class="error-text">'+esc(e.message)+'</p>';}
    }
    document.querySelector("#ticketCreateForm")?.addEventListener("submit",async e=>{e.preventDefault();const payload={title:document.querySelector("#ticketTitle").value.trim(),category:document.querySelector("#ticketCategory").value,body:document.querySelector("#ticketBody").value.trim()};try{await api("/api/support/tickets",{method:"POST",body:JSON.stringify(payload)});e.target.reset();toast("تیکت با موفقیت ثبت شد.");await loadTickets();}catch(err){toast(err.message);}});
    await loadTickets();
  }
  async function initAdmin(){
    const root=document.querySelector("#adminDashboard");if(!root)return;
    try{
      const data=await api("/api/admin/dashboard"),c=data.counts;
      root.innerHTML='<div class="admin-metrics">'+[['کل کاربران',c.users],['خریداران',c.buyers],['فروشندگان',c.sellers],['کالاها',c.listings],['ویترین‌ها',c.stores],['درآمد ثبت‌شده',fmt.format(data.revenue_toman)+' تومان'],['تیکت‌های باز',c.open_tickets],['گزارش‌های باز',c.open_reports],['حساب‌های مسدود',c.banned]].map(([label,value])=>'<article class="metric-card"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong></article>').join("")+'</div><section class="page-panel"><h2>مدیریت کاربران</h2><div class="table-wrap"><table class="admin-table"><thead><tr><th>کاربر</th><th>شماره</th><th>نقش</th><th>ثبت‌نام</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>'+data.users.map(u=>'<tr><td>'+esc(u.name)+'</td><td>'+esc(u.phone)+'</td><td>'+esc(u.role)+'</td><td>'+date(u.created_at)+'</td><td>'+(u.is_banned?'مسدود':'فعال')+'</td><td>'+(u.phone===window.KIDAREH_ADMIN_PHONE?'مدیر اصلی':'<button class="button button-outline" type="button" data-ban="'+u.id+'" data-state="'+(u.is_banned?'1':'0')+'">'+(u.is_banned?'رفع مسدودی':'مسدود کردن')+'</button>')+'</td></tr>').join("")+'</tbody></table></div></section><section class="page-panel"><h2>تیکت‌های پشتیبانی</h2><div class="table-wrap"><table class="admin-table"><thead><tr><th>#</th><th>موضوع</th><th>کاربر</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>'+data.tickets.map(t=>'<tr><td>'+fmt.format(t.id)+'</td><td>'+esc(t.title)+'</td><td>'+esc(t.user_name)+' · '+esc(t.phone)+'</td><td>'+esc(t.status)+'</td><td><a href="/support">ورود به پشتیبانی</a> <button class="button button-outline" data-close-ticket="'+t.id+'" type="button">بستن</button></td></tr>').join("")+'</tbody></table></div></section><section class="page-panel"><h2>فعالیت‌های اخیر</h2><div class="community-list">'+data.activity.map(a=>'<article class="community-list-item"><strong>'+esc(a.label)+'</strong><small>'+({listing:"ثبت کالا",user:"ثبت‌نام کاربر",ticket:"تیکت پشتیبانی"}[a.type]||esc(a.type))+' · '+date(a.created_at)+'</small></article>').join("")+'</div></section>';
      root.querySelectorAll("[data-ban]").forEach(b=>b.addEventListener("click",async()=>{const banned=b.dataset.state!=="1";const reason=banned?(prompt("علت مسدودسازی (اختیاری):")||""):"";try{await api("/api/admin/users/"+b.dataset.ban,{method:"PATCH",body:JSON.stringify({is_banned:banned,reason})});toast("وضعیت کاربر به‌روزرسانی شد.");await initAdmin();}catch(e){toast(e.message);}}));
      root.querySelectorAll("[data-close-ticket]").forEach(b=>b.addEventListener("click",async()=>{try{await api("/api/admin/tickets/"+b.dataset.closeTicket,{method:"PATCH",body:JSON.stringify({status:"closed"})});toast("تیکت بسته شد.");await initAdmin();}catch(e){toast(e.message);}}));
    }catch(e){root.innerHTML='<div class="page-panel"><h2>دسترسی یا دریافت اطلاعات ممکن نشد</h2><p class="error-text">'+esc(e.message)+'</p><p class="muted">برای ورود به داشبورد، شماره مدیر باید در متغیر ADMIN_PHONE سرور تنظیم و با پیامک تأیید شده باشد.</p></div>';}
  }
  document.addEventListener("DOMContentLoaded",()=>{initMessages();initSupport();initAdmin();});
})();