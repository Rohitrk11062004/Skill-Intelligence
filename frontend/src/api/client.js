import axios from 'axios';
import { clearCache, getCached, makeCacheKey, setCached } from './cache';

const normalizeBaseUrl = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return raw;
  // Avoid subtle 404s on case-sensitive routers (FastAPI paths are case-sensitive).
  return raw.replace(/\/api\/V1\b/, '/api/v1');
};

const api = axios.create({
  baseURL: normalizeBaseUrl(import.meta.env.VITE_API_URL) || 'http://localhost:8000/api/v1',
});

// Cached GETs to reduce latency across pages.
// - Cache is session-scoped (in-memory) and safe to invalidate on write operations.
// - Default TTL: 5 minutes.
const GET_CACHE_TTL_MS = 5 * 60 * 1000;

// Request interceptor to add JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const method = String(config.method || 'get').toLowerCase();
  if (method === 'get' && !config.headers?.['x-skip-cache']) {
    const key = makeCacheKey({
      method,
      url: config.url,
      params: config.params,
      token,
    });
    const cached = getCached(key);
    if (cached) {
      // Short-circuit axios by providing a custom adapter.
      config.adapter = async () => ({
        data: cached,
        status: 200,
        statusText: 'OK',
        headers: { 'x-cache': 'HIT' },
        config,
        request: null,
      });
    } else {
      config.headers['x-cache-key'] = key;
    }
  }
  return config;
});

// Response interceptor to handle 401s
api.interceptors.response.use(
  (response) => {
    const method = String(response?.config?.method || 'get').toLowerCase();
    if (method === 'get') {
      const key = response?.config?.headers?.['x-cache-key'];
      if (key) {
        setCached(key, response.data, { ttlMs: GET_CACHE_TTL_MS });
      }
    } else {
      // Any write can change downstream GET results; clear GET cache.
      clearCache('get|');
    }
    return response;
  },
  (error) => {
    // Clear GET cache on auth invalidation.
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      clearCache('get|');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
