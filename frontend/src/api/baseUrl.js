/**
 * API base for axios/fetch.
 * - Vite dev: use /api (proxied to backend in vite.config.js)
 * - Production / other hosts: http://{hostname}:8005/api (must match backend port)
 */
export function resolveApiBaseURL() {
  const envBase = import.meta?.env?.VITE_API_BASE
  if (envBase && typeof envBase === 'string') return envBase

  if (import.meta.env.DEV) {
    return '/api'
  }

  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `http://${window.location.hostname}:8005/api`
  }

  return '/api'
}
