// Le fil : service worker (notifications appli fermée, ouverture hors ligne de la page)
const CACHE = "le-fil-v7";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(["./", "./index.html", "./manifest.webmanifest"])).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
    await self.clients.claim();
  })());
});

// La page vient toujours du réseau en priorité ; la copie sert seulement hors connexion
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith((async () => {
    try {
      // Toujours redemander la page au serveur (pas de copie périmée du navigateur)
      const r = await fetch(e.request, { cache: "no-cache" });
      const c = await caches.open(CACHE);
      c.put("./index.html", r.clone());
      return r;
    } catch (_) {
      return (await caches.match("./index.html")) || Response.error();
    }
  })());
});

self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { corps: e.data ? e.data.text() : "" }; }
  e.waitUntil((async () => {
    const fenetres = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    // Pas de notification si Le fil est déjà ouvert et au premier plan
    if (fenetres.some((f) => f.visibilityState === "visible" && f.focused)) return;
    await self.registration.showNotification(d.titre || "Le fil", {
      body: d.corps || "Nouveau message",
      tag: "le-fil",
      renotify: true,
      icon: "icone-192.png",
      badge: "icone-badge.png",
      data: { url: self.registration.scope },
    });
  })());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil((async () => {
    const fenetres = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const f of fenetres) {
      if ("focus" in f) return f.focus();
    }
    return self.clients.openWindow(self.registration.scope);
  })());
});
