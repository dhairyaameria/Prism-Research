import type { NextConfig } from "next";

/** API proxy is `app/api/prism/[[...path]]/route.ts` (streams SSE). Legacy rewrite kept for old bookmarks. */
const apiProxyTarget = (process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/prism-api/:path*", destination: `${apiProxyTarget}/:path*` }];
  },
};

export default nextConfig;
