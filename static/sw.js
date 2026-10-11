/* کی‌داره — Service Worker
   CACHE_VERSION را با هر انتشار افزایش بده تا کاربران نسخهٔ جدید را دریافت کنند. */
"use strict";

const CACHE_VERSION = "v5";
const SHELL_CACHE = `kidareh-shell-${CACHE_VERSION}`;
const RUNTIME_CACHE = `kidareh-runtime-${CACHE_VERSION}`;
const KNOWN_CACHES = [SHELL_CACHE, RUNTIME_CACHE];

const PRECACHE_ASSETS = [
  "/static/offline.html",
  "/static/css/style.css",
  "/static/css/pages.css",
  "/static/css/components.css",
  "/static/css/theme-mh.css",
  "/static/css/site-shell.css",
  "/static/js/ui.js",
  "/static/js/pwa-rules.js",
  "/static/js/app.js",
  "/static/manifest.webmanifest",
  "/static/fonts/Vazirmatn-Variable.woff2",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon-192-maskable.png",
  "/static/icons/icon-512-maskable.png"
];

const PRIVATE_PATH = /^\/(account|seller|admin|messages|support|monetization|saved|following)(\/|$)/;
const API_PATH = /^\/api\//;
const CATALOG_PATH = /^\/(search|stores)\/?$/;
const PRODUCT_PATH = /^\/product\/[^/]+\/?$/;
const STORE_PATH = /^\/store\/[^/]+\/?$/;

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    // یک فایل اختیاری که در دسترس نیست، نصب Service Worker را متوقف نمی‌کند.
    await Promise.allSettled(PRECACHE_ASSETS.map(async asset => {
      const response = await fetch(asset, { cache: "reload" });
      if (response.ok) await cache.put(asset, response);
    }));
  })());
});

// پیام SKIP_WAITING از صفحه، بعد از تأیید کاربر (Toast «بروزرسانی») ارسال می‌شود.
self.addEventListener("message", event => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys
      .filter(key => key.startsWith("kidareh-") && !KNOWN_CACHES.includes(key))
      .map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request) || await caches.match(request);
    if (cached) return cached;
    return (await caches.match("/static/offline.html")) ||
      new Response("ارتباط برقرار نشد، دوباره امتحان می‌کنیم؟", {
        status: 503,
        headers: { "Content-Type": "text/plain; charset=utf-8" }
      });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request).then(response => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);
  if (cached) {
    network.catch(() => {}); // بازبینی در پس‌زمینه؛ خطای شبکه پاسخ کش‌شده را خراب نمی‌کند
    return cached;
  }
  return (await network) || (await caches.match("/static/offline.html")) ||
    new Response("", { status: 503 });
}

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (PRIVATE_PATH.test(url.pathname) || API_PATH.test(url.pathname)) return;

  // صفحات catalog / stores: stale-while-revalidate
  if (request.mode === "navigate" && CATALOG_PATH.test(url.pathname)) {
    event.respondWith(staleWhileRevalidate(request, RUNTIME_CACHE));
    return;
  }

  // صفحات محصول / ویترین: network-first با fallback به cache
  if (request.mode === "navigate" && (PRODUCT_PATH.test(url.pathname) || STORE_PATH.test(url.pathname))) {
    event.respondWith(networkFirst(request, RUNTIME_CACHE));
    return;
  }

  if (request.mode === "navigate" && url.pathname === "/") {
    event.respondWith(networkFirst(request, RUNTIME_CACHE));
    return;
  }

  // دارایی‌های استاتیک: cache-first با به‌روزرسانی پس‌زمینه (SWR)
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(staleWhileRevalidate(request, SHELL_CACHE));
  }
});
