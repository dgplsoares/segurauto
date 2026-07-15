// POST /api/support → POST /support/chat (ai-service). Repassa o Bearer da sessão (anti-IDOR no backend).
import type { NextRequest } from "next/server";

import { proxyJson } from "@/lib/bff";

export async function POST(req: NextRequest): Promise<Response> {
  const body = await req.json();
  const auth = req.headers.get("authorization");
  return proxyJson("/support/chat", {
    body,
    headers: auth ? { Authorization: auth } : {},
  });
}
