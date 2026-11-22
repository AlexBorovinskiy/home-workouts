const CACHE='home-workouts-anatomy-v2';
const CORE=['./','./index.html','./manifest.webmanifest'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(Promise.all([self.clients.claim(),caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('home-workouts-anatomy-')&&k!==CACHE).map(k=>caches.delete(k))))]))});
self.addEventListener('fetch',e=>{
 if(e.request.method!=='GET'||(!e.request.url.startsWith(self.location.origin)&&!e.request.url.startsWith('https://cdn.jsdelivr.net/')&&!e.request.url.startsWith('https://charleeh.github.io/')))return;
 e.respondWith(caches.match(e.request).then(cached=>cached||fetch(e.request).then(resp=>{if(resp.ok||resp.type==='opaque'){const saved=resp.clone();caches.open(CACHE).then(cache=>cache.put(e.request,saved)).catch(()=>{});}return resp;})));
});