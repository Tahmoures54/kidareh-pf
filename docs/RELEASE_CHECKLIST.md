# چک‌لیست انتشار کی‌داره — نسخهٔ پیشنهادی `v1.0.0`

> وضعیت هر مورد با یکی از برچسب‌های زیر مشخص شده است:
> ✅ انجام و تست‌شده · 🟡 انجام شده ولی نیاز به تست دستی/محیط واقعی دارد · ⏳ انجام نشده (در این نسخه)

## ۱. کیفیت کد و تست‌ها
- ✅ `python -m pytest -q` — ۱۴۳ تست سبز (شامل `tests/test_release_smoke.py`، `tests/test_structural_basics.py` و `tests/test_release_ux.py`)
- ✅ `node --check` روی تمام فایل‌های JS (در `tests.yml` اضافه شد: `ui.js`، `pwa-rules.js`، `onboarding.js`)
- ✅ منطق نمایش بنر نصب (۱۵ ثانیه / اسکرول ۵۰٪ / کلیک محصول / dismiss ۷ روزه / iOS) با Node تست می‌شود
- ✅ `console.log` و `debug=True` در کد نهایی وجود ندارد (تست `test_no_console_log_or_debug_true_in_shipped_code`)
- ✅ `SECRET_KEY` از ENV خوانده می‌شود و در production بدون مقدار قوی، اپ بالا نمی‌آید

## ۲. طراحی و UX
- ✅ Design tokens در `static/css/style.css` (پالت، شعاع، سایه، spacing 4/8/12/16/24/32، تایپوگرافی)
- ✅ Dark mode خودکار با `prefers-color-scheme` (سطوح اصلی؛ بعضی صفحات قدیمی هنوز رنگ ثابت دارند)
- ✅ فونت Vazirmatn (متغیر) self-hosted در `static/fonts/` با `font-display: swap`؛ حذف کامل Google Fonts
- ✅ `<html lang="fa" dir="rtl">`؛ تبدیل خصوصیات فیزیکی به logical properties در CSS و قالب‌ها
- ✅ کامپوننت‌های پایه در `static/css/components.css` (Button، Input، Card، Badge، Modal، Toast، Skeleton، Empty state)
- ✅ `fadeInUp` و `prefers-reduced-motion`؛ `focus-visible` واضح؛ حداقل ۴۴px برای دکمه‌ها
- ✅ Bottom tab bar با ۴ تب: خانه، جست‌وجو، ثبت، پروفایل
- ✅ Toast یکپارچه (`static/js/ui.js`) و Optimistic UI helper
- ✅ تور ۳ مرحله‌ای اولین ورود (`static/js/onboarding.js`) با ذخیره در localStorage
- 🟡 Microcopy انسانی: پیام‌های اصلی PWA و Toast بازنویسی شده‌اند؛ بقیهٔ پیام‌های خطا در صفحات قدیمی هنوز باید بازبینی شوند
- ⏳ AIDA صفحهٔ اصلی: CTA دوم («ساخت ویترین فروشگاه») حذف نشده؛ نمایش آماری «تعداد کاربران/آگهی‌های فعال» نیاز به endpoint آماری دارد
- ⏳ کاهش فرم چندمرحله‌ای ثبت آگهی (progress indicator) و ورود OTP-first برای مهمان‌ها: در این نسخه پیاده نشده
- ⏳ Social proof (امتیاز فروشگاه، بازدید آگهی، نشان فروشنده تأییدشده): داده‌های لازم در مدل فعلی وجود ندارد

## ۳. PWA
- ✅ `manifest.webmanifest`: `display: standalone`، `start_url: /?utm_source=pwa`، `lang: fa`، `dir: rtl`، `theme_color: #0E7490`
- ✅ آیکون‌های 192/512 (any و maskable) در `static/icons/`، آیکون iOS (`apple-touch-icon`)
- ✅ Shortcuts: جستجو، ثبت آگهی، پیام‌ها
- ✅ `sw.js` با `CACHE_VERSION = "v4"`؛ precache شامل offline، CSS، `app.js`، manifest، فونت و آیکون‌ها
- ✅ Runtime: stale-while-revalidate برای `/search` و `/stores`؛ network-first برای `/product/*` و `/store/*`
- ✅ `skipWaiting` با تأیید کاربر (Toast «بروزرسانی») + `clients.claim`؛ بعد از کنترل‌شدن، Toast «نسخه‌ی جدید نصب شد 🎉»
- ✅ بنر نصب سفارشی (`beforeinstallprompt` ذخیره می‌شود) با «نصب» و «بعداً»؛ راهنمای iOS با آیکون اشتراک‌گذاری
- ✅ رویداد `appinstalled` و `pwa_*` به `dataLayer` (در صورت وجود) و `kidareh:analytics` ارسال می‌شود
- ✅ `offline.html` با «تلاش دوباره» و فهرست صفحه‌های کش‌شده
- ⏳ Background Sync برای فرم‌های آگهی/پیام: پیاده نشده (نیاز به صف IndexedDB و تست روی مرورگرهای واقعی)
- 🟡 بنر نصب فقط روی مرورگرهایی که `beforeinstallprompt` دارند (Chromium) و iOS راهنما نشان می‌دهد؛ رفتار واقعی روی گوشی باید تست شود

## ۴. SEO
- ✅ Open Graph (`og:title`, `og:image` با fallback لوگو، `og:type`)، Twitter Card (`summary_large_image`)، canonical
- ✅ JSON-LD `Product` (قیمت IRR، تصویر، شهر) در صفحهٔ کالا و `LocalBusiness` (آدرس) در صفحهٔ ویترین
- ✅ `/sitemap.xml` پویا (صفحات عمومی + فروشگاه‌ها + کالاها) و `/robots.txt` (با Disallow برای بخش‌های خصوصی)
- ⏳ URLهای slugified: `/product/<id>` و `/store/<id>` باقی مانده‌اند

## ۵. عملکرد و Lighthouse
- ✅ حذف render-blocking از فونت (preload + swap) و حذف درخواست‌های Google
- ✅ اسکریپت‌های جدید `defer` هستند
- ⏳ Lighthouse موبایل: **اجرا نشد.** محیط فعلی مرورگر Chrome ندارد و دسترسی به دانلود Chrome وجود ندارد. باید روی محیط staging اجرا شود و نتایج اینجا ثبت شود:

  | معیار | هدف | نتیجه |
  |---|---|---|
  | Performance | ≥ 90 | — |
  | Accessibility | ≥ 95 | — |
  | Best Practices | ≥ 95 | — |
  | SEO | ≥ 95 | — |
  | PWA قابل نصب | بله | — |

- ⏳ Minify/bundle CSS و JS، Cache-Control یک‌ساله برای فایل‌های hash‌دار، sprite SVG برای آیکون‌ها: در این نسخه انجام نشده (فایل‌ها hash ندارند)

## ۶. تست دستی روی دستگاه‌ها
- ⏳ Chrome Android — نصب، بنر، بروزرسانی Service Worker
- ⏳ Safari iOS — راهنمای Add to Home Screen، safe-area نوار پایین
- ⏳ Firefox و Samsung Internet
- ⏳ RTL و dark mode روی هر کدام

## ۷. انتشار (مرحله‌های نیازمند دسترسی مدیر مخزن)
- ⏳ ساخت `release/v1.0.0`، merge به `main` با `--no-ff`، تگ `v1.0.0` و push
- ⏳ اجرای `python scripts/backup_sqlite.py` قبل از دیپلوی روی محیط واقعی
- ⏳ بررسی `tests.yml` و `deploy-liara.yml` و Health check (`/api/health`)

## ۸. برنامهٔ بازگشت (Rollback)
1. آخرین تگ پایدار قبلی را پیدا کن (`git tag --sort=-v:refname | head`).
2. روی Liara، نسخهٔ تگ قبلی را دیپلوی کن.
3. اگر دیتابیس تغییر کرده، فایل پشتیبان را با `python scripts/restore_sqlite.py <backup-file>` برگردان.
4. `CACHE_VERSION` در `static/sw.js` را بالاتر ببر تا کاربران PWA کش نامعتبر را پاک کنند.

## ۹. نسخه و Changelog (پیشنهادی `v1.0.0`)
- **feat:** سیستم طراحی (tokens، dark mode، کامپوننت‌ها)، فونت self-hosted، bottom nav چهار تبی، تور اولین ورود، تست‌های UX/PWA/SEO
- **feat(pwa):** بنر نصب هوشمند، راهنمای iOS، Toast بروزرسانی، shortcuts، آیکون maskable، offline با کش
- **feat(seo):** JSON-LD، sitemap و robots
- **fix:** `start_url` به `utm_source=pwa` تغییر کرد؛ دسترسی به Google Fonts حذف شد
