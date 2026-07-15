// POST /api/support/sessions/{id}/confirm → dispara as ações da confirmação (ai-service). Repassa o Bearer.
import type { NextRequest } from "next/server";

import { proxyJson } from "@/lib/bff";

export async function POST(req: NextRequest, { params }: { params: { id: string } }): Promise<Response> {
  const body = await req.json();
  const auth = req.headers.get("authorization");
  return proxyJson(`/support/sessions/${encodeURIComponent(params.id)}/confirm`, {
    body,
    headers: auth ? { Authorization: auth } : {},
  });
}
