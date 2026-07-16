// GET /api/auth/session → GET /auth/session (ai-service). 200 {lead_id} | 401.
// Usado na rehidratação: valida o token persistido no localStorage antes de mostrar a UI autenticada.
import type { NextRequest } from "next/server";

import { proxyJson } from "@/lib/bff";

export async function GET(req: NextRequest): Promise<Response> {
  const auth = req.headers.get("authorization");
  return proxyJson("/auth/session", {
    method: "GET",
    headers: auth ? { Authorization: auth } : {},
  });
}
