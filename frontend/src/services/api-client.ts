import axios from "axios";

// בצד השרת (SSR) נשתמש בכתובת המלאה. בצד הלקוח נפנה ל-Proxy היחסי
const baseURL = typeof window === "undefined"
  ? "https://ssos-backend.onrender.com/api"
  : "/api";

const apiClient = axios.create({
  baseURL,
  withCredentials: true, // קריטי: מורה לדפדפן להעביר ולקבל עוגיות סשן HttpOnly
  headers: {
    "Content-Type": "application/json",
  },
});

// Interceptor לתגובות נכנסות
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const errorMessage = error.response?.data?.message || "אירעה שגיאה בתקשורת עם השרת";

    // אנו לא מבצעים ניתוב מחדש כאן כדי למנוע לולאות הפניה בעמוד ה-Login.
    // ה-AuthProvider ינהל את הניתוב בצורה מבוקרת בצד הלקוח.
    return Promise.reject({
      ...error,
      status,
      friendlyMessage: errorMessage,
    });
  }
);

export default apiClient;
