// edge/worker.js
// CloudFlare Worker for caching and proxying toilet-map API requests.
// Related: batch/api_server.py

const API_ORIGIN = 'https://toilet-map.example.com';
const CACHE_TTL = 300; // 5 minutes

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const cacheKey = new Request(url.toString(), request);
    const cache = caches.default;

    // Try cache first
    const cachedResponse = await cache.match(cacheKey);
    if (cachedResponse) {
      return cachedResponse;
    }

    // Forward to origin
    const originUrl = `${API_ORIGIN}${url.pathname}${url.search}`;
    const response = await fetch(originUrl, {
      method: request.method,
      headers: request.headers,
    });

    // Cache successful responses
    if (response.ok) {
      const headers = new Headers(response.headers);
      headers.set('cache-control', `public, max-age=${CACHE_TTL}`);
      headers.set('cf-cache-status', 'HIT');
      const cached = new Response(response.body, {
        status: response.status,
        headers,
      });
      ctx.waitUntil(cache.put(cacheKey, cached.clone()));
      return cached;
    }

    return response;
  },
};
