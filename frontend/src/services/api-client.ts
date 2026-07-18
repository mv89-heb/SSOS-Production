import axios from "axios";

const apiClient = axios.create({
  // הגדרה קבועה ואחידה של הכתובת היחסית דרך ה-Proxy
  baseURL: "/api",
  withCredentials: true, // חובה עבור עוגיות סשן HttpOnly
  headers: {
    "Content-Type": "application/json",
  },
});

// אינטרספטור לתגובות נכנסות
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const errorMessage = error.response?.data?.message || "אירעה שגיאה בתקשורת עם השרת";

    return Promise.reject({
      ...error,
      status,
      friendlyMessage: errorMessage,
    });
  }
);

export default apiClient;
