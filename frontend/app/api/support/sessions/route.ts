// POST /api/support/sessions → POST /support/sessions (ai-service). Cria a sessão de cotação (multi-turn).
import type { NextRequest } from "next/server";

import { proxyJson } from "@/lib/bff";

export async function POST(req: NextRequest): Promise<Response> {
  const body = await req.json().catch(() => ({}));
  const auth = req.headers.get("authorization");
  return proxyJson("/support/sessions", { body, headers: auth ? { Authorization: auth } : {} });
}
