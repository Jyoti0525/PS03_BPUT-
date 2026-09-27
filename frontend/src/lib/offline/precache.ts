/**
 * Ask the service worker to keep this page and every build asset it has loaded, so the page
 * reopens with no network (a kiosk link loaded once at the camp keeps working offline).
 */
export async function precacheCurrentPage() {
  if (typeof window === "undefined" || !("serviceWorker" in navigator) || !navigator.onLine) return;
  try {
    const reg = await navigator.serviceWorker.ready;
    const assets = performance
      .getEntriesByType("resource")
      .map((e) => new URL(e.name))
      .filter((u) => u.origin === location.origin && (u.pathname.startsWith("/_next/static/") || /\.(png|svg|woff2?|ico)$/.test(u.pathname)))
      .map((u) => u.pathname + u.search);
    reg.active?.postMessage({ type: "precache", urls: [location.pathname, ...new Set(assets)] });
  } catch {
    /* no service worker (dev or unsupported) */
  }
}
