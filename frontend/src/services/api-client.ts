import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

if (typeof window !== "undefined" && !process.env.NEXT_PUBLIC_API_URL && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
  console.error("[SSOS] NEXT_PUBLIC_API_URL is not set — falling back to " + API_BASE_URL + ". API calls will fail.");
}

const apiClient = axios.create({ baseURL: API_BASE_URL, withCredentials: true, headers: { "Content-Type": "application/json" } });
const SAFE_METHODS = new Set(["get", "head", "options"]);
type RetryableRequestConfig = NonNullable<Parameters<typeof apiClient.request>[0]> & { _csrfRetry?: boolean };
let csrfTokenPromise: Promise<string> | null = null;

async function fetchCsrfToken(): Promise<string> {
  const { data } = await axios.get<{ success: boolean; csrf_token: string }>(`${apiClient.defaults.baseURL}/api/auth/csrf-token`, { withCredentials: true });
  return data.csrf_token;
}

export function resetCsrfToken() { csrfTokenPromise = null; }

apiClient.interceptors.request.use(async (config) => {
  const method = (config.method || "get").toLowerCase();
  if (config.data instanceof FormData) {
    // Let the browser set multipart/form-data with its boundary. The global
    // JSON content type otherwise makes Flask request.files empty.
    if (config.headers) delete config.headers["Content-Type"];
  }
  if (!SAFE_METHODS.has(method)) {
    if (!csrfTokenPromise) csrfTokenPromise = fetchCsrfToken();
    try {
      const token = await csrfTokenPromise;
      config.headers = config.headers ?? {};
      config.headers["X-CSRFToken"] = token;
    } catch {
      csrfTokenPromise = null;
    }
  }
  return config;
});

apiClient.interceptors.response.use((response) => response, async (error) => {
  const status = error.response?.status;
  const errorMessage = String(error.response?.data?.message || "");
  const normalizedMessage = errorMessage.toLowerCase();
  const requestConfig = error.config as RetryableRequestConfig | undefined;
  const method = String(requestConfig?.method || "get").toLowerCase();
  const isCsrfFailure = !SAFE_METHODS.has(method) && (status === 400 || status === 403) && (normalizedMessage.includes("csrf") || normalizedMessage.includes("cross-site request forgery") || normalizedMessage.includes("token"));
  if (isCsrfFailure && requestConfig && !requestConfig._csrfRetry) {
    requestConfig._csrfRetry = true;
    resetCsrfToken();
    return apiClient.request(requestConfig);
  }
  if (status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login") window.location.href = "/login";
  return Promise.reject({ ...error, friendlyMessage: errorMessage || "אירעה שגיאה בתקשורת עם השרת" });
});

export { apiClient };
export default apiClient;
