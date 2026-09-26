import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Restart the API server on Render. Runs on the web server only, so the Render API key never
 * reaches the browser. Allowed for signed-in facility supervisors (JWT verified with the same
 * secret the API uses). Waking a sleeping server needs no restart — any request wakes it.
 *
 * Env: RENDER_API_KEY, RENDER_SERVICE_ID, JEEVIA_JWT_SECRET
 */
export const dynamic = "force-dynamic";

const COOLDOWN_MS = 60_000;
let lastRestart = 0;

function b64url(buf: Buffer) {
  return buf.toString("base64").replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function verify(token: string, secret: string): Record<string, unknown> | null {
  const [h, p, sig] = token.split(".");
  if (!h || !p || !sig) return null;
  const expected = b64url(createHmac("sha256", secret).update(`${h}.${p}`).digest());
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    const header = JSON.parse(Buffer.from(h, "base64url").toString());
    if (header.alg !== "HS256") return null;
    const claims = JSON.parse(Buffer.from(p, "base64url").toString());
    if (typeof claims.exp !== "number" || claims.exp * 1000 < Date.now()) return null;
    return claims;
  } catch {
    return null;
  }
}

const configured = () => !!(process.env.RENDER_API_KEY && process.env.RENDER_SERVICE_ID && process.env.JEEVIA_JWT_SECRET);

export async function GET() {
  return Response.json({ configured: configured() }, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: Request) {
  if (!configured()) return Response.json({ message: "Server restart is not configured" }, { status: 501 });
  const token = (request.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  const claims = verify(token, process.env.JEEVIA_JWT_SECRET!);
  if (!claims || claims.typ !== "access") return Response.json({ message: "Sign in again to restart the server" }, { status: 401 });
  if (claims.role !== "supervisor") return Response.json({ message: "Only facility supervisors can restart the server" }, { status: 403 });
  if (Date.now() - lastRestart < COOLDOWN_MS) return Response.json({ message: "A restart was just requested — wait a minute" }, { status: 429 });

  const r = await fetch(`https://api.render.com/v1/services/${process.env.RENDER_SERVICE_ID}/restart`, {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.RENDER_API_KEY}`, Accept: "application/json" },
  });
  if (!r.ok) return Response.json({ message: `Render refused the restart (${r.status})` }, { status: 502 });
  lastRestart = Date.now();
  return Response.json({ message: "Restart requested — the server will be back in about a minute" });
}
