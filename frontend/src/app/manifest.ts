import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "CORP - HiRo",
    short_name: "CORP - HiRo",
    description: "Корпоративная система управления CORP - HiRo",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#111923",
    theme_color: "#111923",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
      {
        src: "/icon-512-maskable.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
