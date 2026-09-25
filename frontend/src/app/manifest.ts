import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Jeevia — Triage support",
    short_name: "Jeevia",
    description: "Human-in-the-loop triage support for Indian health facilities. Educational prototype.",
    start_url: "/kiosk",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#f6f6fa",
    theme_color: "#16182b",
    categories: ["medical", "health"],
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Patient intake", url: "/kiosk" },
      { name: "Triage queue", url: "/reviewer" },
    ],
  };
}
