import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";


const withNextIntl =
  createNextIntlPlugin(
    "./src/i18n/request.ts"
  );


const nextConfig: NextConfig = {

  reactStrictMode: true,


  async rewrites() {

    return [
      {
        source: "/api/:path*",
        destination:
          "https://ssos-backend.onrender.com/api/:path*",
      },
    ];

  },

};


export default withNextIntl(nextConfig);
