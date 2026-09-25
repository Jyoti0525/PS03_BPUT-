import type { JeeviaApi } from "./contract";
import { liveApi } from "./live";
import { mockApi } from "./mock/server";

/**
 * `NEXT_PUBLIC_API_MODE=live` talks to FastAPI at NEXT_PUBLIC_API_URL.
 * Anything else (the default) uses the in-browser mock so the UI never blocks on the API.
 */
export const API_MODE: "mock" | "live" = process.env.NEXT_PUBLIC_API_MODE === "live" ? "live" : "mock";

export const api: JeeviaApi = API_MODE === "live" ? liveApi : mockApi;

export { ApiError } from "./contract";
export { getDeviceId } from "./tokens";
