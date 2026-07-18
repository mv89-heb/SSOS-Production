// next.config.ts
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  reactStrictMode: true,
  
  // הזרקת חוק ה-Rewrites עבור ה-Proxy
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
