// Same-origin proxy for public and administrator v2 API requests.
import type { NextRequest } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";
type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const upstream = new URL(`/api/v2/${path.join("/")}`, API_BASE_URL);
  upstream.search = request.nextUrl.search;
  const headers: Record<string, string> = {
    accept: request.headers.get("accept") ?? "application/json",
  };
  const contentType = request.headers.get("content-type");
  const adminKey = request.headers.get("x-admin-key");
  if (contentType) headers["content-type"] = contentType;
  if (adminKey) headers["x-admin-key"] = adminKey;

  try {
    const response = await fetch(upstream, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
    });
    return new Response(response.body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    });
  } catch {
    return Response.json({ detail: "backend unavailable" }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
