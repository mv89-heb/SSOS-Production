import axios, { InternalAxiosRequestConfig } from "axios";

/**
 * Axios client aligned with the backend auth model:
 *  - Flask-Login session cookies (HttpOnly) — hence withCredentials: true.
 *  - NO JWT and NO localStorage. The browser carries the session cookie.
 *  - Flask-WTF CSRF: mutating requests must echo a token (issued by
 *    GET /api/auth/csrf-token, tied to the session) in the X-CSRFToken header.
 *
 * NEXT_PUBLIC_API_URL is the backend ORIGIN only (e.g.
 * https://ssos-backend.onrender.com) — service calls already include /api.
 */
export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "",
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

// --- CSRF token management ---------------------------------------------------
let csrfToken: string | null = null;
let csrfFetch: Promise<string> | null = null;

async function getCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  // Deduplicate concurrent fetches (e.g. several mutations firing together)
  if (!csrfFetch) {
    csrfFetch = axios
      .get<{ success: boolean; csrf_token: string }>(
        `${apiClient.defaults.baseURL}/api/auth/csrf-token`,
        { withCredentials: true }
      )
      .then((res) => {
        csrfToken = res.data.csrf_token;
        return csrfToken;
      })
      .finally(() => {
        csrfFetch = null;
      });
  }
  return csrfFetch;
}

/** Clears the cached CSRF token. Call after logout/login — the token is tied
 *  to the server-side session, so a new session needs a fresh token. */
export function resetCsrfToken(): void {
  csrfToken = null;
}

const MUTATING_METHODS = new Set(["post", "put", "patch", "delete"]);

apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const method = (config.method || "get").toLowerCase();
  if (MUTATING_METHODS.has(method)) {
    try {
      config.headers["X-CSRFToken"] = await getCsrfToken();
    } catch {
      // If the token endpoint is unreachable the request itself will fail
      // with a clearer network/HTTP error — don't mask it here.
    }
  }
  return config;
});

// --- Response handling -------------------------------------------------------
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const errorMessage =
      error.response?.data?.message ||
      error.response?.data?.error ||
      "אירעה שגיאה בתקשורת עם השרת";

    if (status === 401 && typeof window !== "undefined") {
      resetCsrfToken();
      // Redirect only outside the login page to avoid a redirect loop
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }

    // A 400 CSRF rejection means our cached token went stale (session rotated)
    if (status === 400 && String(errorMessage).toLowerCase().includes("csrf")) {
      resetCsrfToken();
    }

    return Promise.reject({ ...error, friendlyMessage: errorMessage });
  }
);

export default apiClient;
