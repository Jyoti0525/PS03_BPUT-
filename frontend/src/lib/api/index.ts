import type { JeeviaApi } from "./contract";
import { liveApi } from "./live";

/**
 * `NEXT_PUBLIC_API_MODE=live` talks to FastAPI at NEXT_PUBLIC_API_URL.
 * Anything else uses the in-browser mock (local development without a backend).
 */
export const API_MODE: "mock" | "live" = process.env.NEXT_PUBLIC_API_MODE === "live" ? "live" : "mock";

/** The mock backend is loaded on first use only, so live builds never download it. */
function lazyMock(): JeeviaApi {
  let mod: Promise<JeeviaApi> | null = null;
  const load = () => (mod ??= import("./mock/server").then((m) => m.mockApi));
  return new Proxy({} as JeeviaApi, {
    get(_, key: string) {
      if (key === "mode") return "mock";
      if (key === "then") return undefined; // not a thenable
      return (...args: unknown[]) => load().then((m) => (m[key as keyof JeeviaApi] as (...a: unknown[]) => unknown)(...args));
    },
  });
}

export const api: JeeviaApi = API_MODE === "live" ? liveApi : lazyMock();

export { ApiError } from "./contract";
export { getDeviceId } from "./tokens";
