import axios from "axios";

const apiClient = axios.create({
  // כל הקריאות עוברות דרך Next.js Rewrite Proxy
  baseURL: "/api",

  // חובה עבור Flask-Login HttpOnly Session Cookie
  withCredentials: true,

  headers: {
    "Content-Type": "application/json",
  },
});

// טיפול מרכזי בשגיאות API
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    const errorMessage =
      error.response?.data?.message ||
      error.response?.data?.error ||
      "אירעה שגיאה בתקשורת עם השרת";

    return Promise.reject({
      ...error,
      status,
      friendlyMessage: errorMessage,
    });
  }
);

// תמיכה בשני סוגי Imports קיימים בפרויקט:
// import apiClient from "@/services/api-client"
// וגם:
// import { apiClient } from "@/services/api-client"

export { apiClient };
export default apiClient;
