import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Отключаем React Strict Mode для production-like поведения в dev
  reactStrictMode: false,

  // Standalone output для production сборки
  output: 'standalone',

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

  webpack(config, { dev, isServer, webpack }) {
    // Next.js 16.1.6 bundles a webpack version where eval-based source maps
    // break pdfjs-dist at runtime with "Object.defineProperty called on non-object".
    // Next restores config.devtool after this hook, so replace its eval plugin
    // with the regular external source-map plugin for the browser compilation.
    if (dev && !isServer) {
      config.plugins = config.plugins.filter(
        (plugin: { constructor?: { name?: string } } | null | undefined) =>
          plugin?.constructor?.name !== "EvalSourceMapDevToolPlugin",
      );
      config.plugins.push(
        new webpack.SourceMapDevToolPlugin({
          filename: "[file].map",
        }),
      );
    }

    return config;
  },
};

export default nextConfig;
