import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

if (
  typeof window !== "undefined" &&
  !process.env.NEXT_PUBLIC_API_URL &&
  window.location.hostname !== "localhost" &&
  window.location.hostname !== "127.0.0.1"
) {
  // This means NEXT_PUBLIC_API_URL was never set at build time on whatever
  // is serving this page, so every apiClient call falls back to
  // http://localhost:5000 — which resolves to the *visitor's own machine*,
  // not your backend. Every request will fail (connection error or, if
  // something else happens to be listening on their :5000, a confusing
  // unrelated 404) and nothing will ever reach the database.
  // eslint-disable-next-line no-console
  console.error(
    "[SSOS] NEXT_PUBLIC_API_URL is not set — falling back to " +
      API_BASE_URL +
      ". API calls will fail. Set NEXT_PUBLIC_API_URL to your backend's URL " +
      "in this service's environment variables and redeploy."
  );
}

// The backend uses Flask-Login HttpOnly session cookies (no JWT/localStorage
// token), so every request must carry credentials, and every state-changing
// request must carry the CSRF token issued by GET /api/auth/csrf-token.
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

const SAFE_METHODS = new Set(["get", "head", "options"]);

let csrfTokenPromise: Promise<string> | null = null;

async function fetchCsrfToken(): Promise<string> {
  const { data } = await axios.get<{ success: boolean; csrf_token: string }>(
    `${apiClient.defaults.baseURL}/api/auth/csrf-token`,
    { withCredentials: true }
  );
  return data.csrf_token;
}

/** Call after logout (or on a 403 CSRF failure) so the next mutating
 * request fetches a fresh token instead of reusing a stale one. */
export function resetCsrfToken() {
  csrfTokenPromise = null;
}

apiClient.interceptors.request.use(async (config) => {
  const method = (config.method || "get").toLowerCase();
  if (!SAFE_METHODS.has(method)) {
    if (!csrfTokenPromise) {
      csrfTokenPromise = fetchCsrfToken();
    }
    try {
      const token = await csrfTokenPromise;
      config.headers = config.headers ?? {};
      config.headers["X-CSRFToken"] = token;
    } catch {
      // If the token fetch itself fails, let the real request go out and
      // fail with the backend's actual error rather than masking it here.
      csrfTokenPromise = null;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const errorMessage = error.response?.data?.message || "אירעה שגיאה בתקשורת עם השרת";

    if (status === 401) {
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }

    return Promise.reject({
      ...error,
      friendlyMessage: errorMessage,
    });
  }
);

export { apiClient };
export default apiClient;
