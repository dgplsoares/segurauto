// POST /api/lead → POST /leads (ai-service). Repassa a Idempotency-Key gerada no client.
import type { NextRequest } from "next/server";

import { proxyJson } from "@/lib/bff";

export async function POST(req: NextRequest): Promise<Response> {
  const body = await req.json();
  const idem = req.headers.get("idempotency-key");
  return proxyJson("/leads", {
    body,
    headers: idem ? { "Idempotency-Key": idem } : {},
  });
}
