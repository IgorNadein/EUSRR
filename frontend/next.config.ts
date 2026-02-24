import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Указываем корень проекта для Turbopack, чтобы не путался с lockfile в корне монорепо
  turbopack: {
    root: __dirname,
  },

  // Отключаем автоматический редирект trailing slash
  // Django требует слэш в конце URL, а Next.js по умолчанию его убирает
  skipTrailingSlashRedirect: true,

  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
  },

  // Полностью отключаем Next.js Dev Tools UI (кружок "N")
  devIndicators: false,
};

export default nextConfig;
