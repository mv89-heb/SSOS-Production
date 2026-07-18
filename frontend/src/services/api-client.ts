import axios from "axios";

// קביעת הכתובת הבסיסית. בשרת נשתמש תמיד בכתובת האבסולוטית המלאה.
const baseURL = typeof window === "undefined"
  ? "https://ssos-backend.onrender.com/api"
  : "/api";

const apiClient = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Interceptor לבקשות יוצאות
apiClient.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      // שליפת הטוקן מכל המקורות האפשריים של הפרונט
      const token = 
        localStorage.getItem("token") || 
        localStorage.getItem("auth_token") || 
        localStorage.getItem("accessToken") ||
        document.cookie.match(/auth_token=([^;]+)/)?.[1];

      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor לתגובות נכנסות
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const errorMessage = error.response?.data?.message || "אירעה שגיאה בתקשורת עם השרת";

    if (status === 401) {
      if (typeof window !== "undefined") {
        // מחיקת טוקנים פגי תוקף
        localStorage.removeItem("token");
        localStorage.removeItem("auth_token");
        localStorage.removeItem("accessToken");
        
        // מניעת לולאת רענון אינסופית בדף ההתחברות
        if (window.location.pathname !== "/login" && !window.location.pathname.endsWith("/login")) {
          window.location.href = "/login";
        }
      }
    }

    return Promise.reject({
      ...error,
      friendlyMessage: errorMessage,
    });
  }
);

export default apiClient;
