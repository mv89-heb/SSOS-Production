import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  reactStrictMode: true,
  
  // הגדרת פרוקסי מאובטח לעקיפת בעיות CORS ותמיכה בפניות יחסיות
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "https://ssos-backend.onrender.com/api/:path*",
      },
    ];
  },
};

export default withNextIntl(nextConfig);
