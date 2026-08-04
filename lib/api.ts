const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
const configuredApiIsLocalhost = configuredApiUrl
  ? /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(?:\/|$)/i.test(configuredApiUrl)
  : false;

/**
 * Browser-facing API origin.
 *
 * Local development uses the standalone FastAPI server. Production defaults
 * to same-origin requests so visitors call the deployed API instead of their
 * own localhost. NEXT_PUBLIC_API_URL remains available for split deployments.
 */
export const API_BASE_URL = (
  (process.env.NODE_ENV !== "production" || !configuredApiIsLocalhost
    ? configuredApiUrl
    : "") ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "")
).replace(/\/$/, "");

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}
