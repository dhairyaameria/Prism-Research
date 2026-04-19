import type { NextRequest } from "next/server";

/** Upstream Prism API (must stream for SSE; Next `rewrites()` can buffer EventSource). */
const TARGET = (process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export const runtime = "nodejs";

/** Vercel serverless ceiling (Pro+). Hobby has a low cap — for long SSE runs prefer `NEXT_PUBLIC_API_URL` (direct to API). */
export const maxDuration = 300;

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

async function proxy(req: NextRequest, pathSegments: string[] | undefined) {
  const sub = pathSegments?.length ? pathSegments.join("/") : "";
  const url = `${TARGET}/${sub}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    const lk = key.toLowerCase();
    if (["host", "connection", "keep-alive", "transfer-encoding"].includes(lk)) return;
    headers.set(key, value);
  });

  const init: RequestInit = {
    method: req.method,
    headers,
    signal: req.signal,
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    Object.assign(init, { duplex: "half" as const });
  }

  const upstream = await fetch(url, init);

  const out = new Headers();
  const ct = upstream.headers.get("content-type");
  if (ct) out.set("content-type", ct);
  out.set("cache-control", "no-store, no-transform, no-cache");
  out.set("x-accel-buffering", "no");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: out,
  });
}

type Ctx = { params: Promise<{ path?: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function POST(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function PUT(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function PATCH(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function OPTIONS() {
  return new Response(null, { status: 204 });
}
