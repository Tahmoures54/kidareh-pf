"use strict";

const CACHE_NAME = "kidareh-shell-v4";
const SHELL_ASSETS = [
  "/static/css/style.css",
  "/static/css/pages.css",
  "/static/css/theme-mh.css",
  "/static/js/app.js",
  "/static/js/pages.js",
  "/static/js/pwa.js",
  "/static/manifest.webmanifest",
  "/static/offline.html"
];

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    // One missing optional asset must not prevent the worker from installing.
    await Promise.allSettled(SHELL_ASSETS.map(async asset => {
      const response = await fetch(asset, { cache: "reload" });
      if (response.ok) await cache.put(asset, response);
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith("kidareh-shell-") && key !== CACHE_NAME)
      .map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

function isPrivatePath(pathname) {
  return /^\/(account|seller|admin|messages|support|monetization)(\/|$)/.test(pathname) ||
    pathname.startsWith("/api/");
}

function isPublicNavigation(pathname) {
  return pathname === "/" ||
    pathname === "/search" ||
    pathname === "/stores" ||
    /^\/(product|store)\/[^/]+\/?$/.test(pathname);
}

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || isPrivatePath(url.pathname)) return;

  if (request.mode === "navigate" && isPublicNavigation(url.pathname)) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const cacheKey = new Request(url.origin + url.pathname);
      try {
        const response = await fetch(request);
        if (response.ok && response.type === "basic") {
          await cache.put(cacheKey, response.clone());
        }
        return response;
      } catch {
        const cached = await cache.match(cacheKey) || await caches.match("/static/offline.html");
        return cached || new Response("اتصال اینترنت برقرار نیست. پس از اتصال دوباره تلاش کنید.", {
          status: 503,
          headers: { "Content-Type": "text/plain; charset=utf-8" }
        });
      }
    })());
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.ok && response.type === "basic") {
          const cache = await caches.open(CACHE_NAME);
          await cache.put(request, response.clone());
        }
        return response;
      } catch {
        const cached = await caches.match(request);
        if (cached) return cached;
        return new Response("", { status: 504, statusText: "Offline" });
      }
    })());
  }
});