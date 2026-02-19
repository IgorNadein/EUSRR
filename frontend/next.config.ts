import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Rewrites не нужны - в production используйте nginx (http://localhost)
  // Для dev можно запустить backend локально на localhost:8000
  
  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
  },
};

export default nextConfig;
