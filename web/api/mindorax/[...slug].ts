import type { VercelRequest, VercelResponse } from "@vercel/node";

function slugToPath(query: VercelRequest["query"]): string {
  const slug = query.slug;
  if (!slug) return "/";
  const parts = Array.isArray(slug) ? slug : [slug];
  const joined = parts.filter(Boolean).join("/");
  return joined ? `/${joined}` : "/";
}

export default async function handler(
  req: VercelRequest,
  res: VercelResponse,
) {
  const origin = process.env.MINDORAX_API_ORIGIN?.replace(/\/$/, "");
  if (!origin) {
    res
      .status(502)
      .json({ error: "MINDORAX_API_ORIGIN is not set (Vercel env, server-only)" });
    return;
  }

  const path = slugToPath(req.query);
  const u = new URL(req.url || "/", "https://internal.local");
  const target = `${origin}${path}${u.search}`;

  const headers = new Headers();
  const forward = ["authorization", "x-admin-key", "content-type", "accept"];
  for (const name of forward) {
    const v = req.headers[name];
    if (typeof v === "string" && v) headers.set(name, v);
  }

  let body: string | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    if (typeof req.body === "string") body = req.body;
    else if (req.body != null) body = JSON.stringify(req.body);
  }

  const backendRes = await fetch(target, {
    method: req.method || "GET",
    headers,
    body,
  });

  const text = await backendRes.text();
  const ct = backendRes.headers.get("content-type");
  if (ct) res.setHeader("content-type", ct);
  res.status(backendRes.status).send(text);
}
