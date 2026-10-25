import type { NextConfig } from "next";

const api = new URL(process.env.VISION_API_ORIGIN ?? "http://127.0.0.1:8000");
// Loopback, or `api`: the packaged compose service, reachable only on the stack's private network (T45).
if (api.protocol !== "http:" || !["127.0.0.1", "localhost", "api"].includes(api.hostname) || api.username || api.password || api.pathname !== "/") {
  throw new Error("VISION_API_ORIGIN must be a loopback or packaged-service HTTP origin");
}

const config: NextConfig = {
  poweredByHeader: false,
  // A cold local embedding query plus bounded consolidation/adjudication exceeds 30 s.
  experimental: { proxyTimeout: 300_000 },
  async rewrites() { return [{ source: "/api/v1/:path*", destination: `${api.origin}/v1/:path*` }]; },
  async headers() { return [{ source: "/:path*", headers: [
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Content-Security-Policy", value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'" },
  ] }]; },
};
export default config;
