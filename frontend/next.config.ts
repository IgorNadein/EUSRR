import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Отключаем автоматический редирект trailing slash
  // Django требует слэш в конце URL, а Next.js по умолчанию его убирает
  skipTrailingSlashRedirect: true,

  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
  },
};

export default nextConfig;
