import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "EUSRR",
    short_name: "EUSRR",
    description: "Корпоративная система управления EUSRR",
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
