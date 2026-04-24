// Simple in-memory cache for GET requests (session-scoped).
// Avoids refetching the same data across pages, reducing latency.

const store = new Map();

function nowMs() {
  return Date.now();
}

function stableStringify(value) {
  if (value === null || value === undefined) return '';
  if (typeof value !== 'object') return String(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((k) => `${k}:${stableStringify(value[k])}`).join(',')}}`;
}

export function makeCacheKey({ method = 'get', url = '', params = null, token = '' } = {}) {
  return `${String(method).toLowerCase()}|${url}|${stableStringify(params)}|t:${token ? '1' : '0'}`;
}

export function getCached(key) {
  const hit = store.get(key);
  if (!hit) return null;
  if (hit.expiresAtMs && nowMs() > hit.expiresAtMs) {
    store.delete(key);
    return null;
  }
  return hit.value;
}

export function setCached(key, value, { ttlMs = 5 * 60 * 1000 } = {}) {
  const expiresAtMs = ttlMs ? nowMs() + ttlMs : 0;
  store.set(key, { value, expiresAtMs });
  return value;
}

export function clearCache(prefix = '') {
  if (!prefix) {
    store.clear();
    return;
  }
  for (const key of store.keys()) {
    if (key.startsWith(prefix)) store.delete(key);
  }
}

