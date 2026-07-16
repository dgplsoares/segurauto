// POST /api/auth/logout → POST /auth/logout (ai-service). Revoga a sessão no servidor.
// Best-effort: mesmo que o upstream falhe (token já inválido), o cliente limpa o localStorage. Sempre 204.
import type { NextRequest } from "next/server";

import { proxyJson } from "@/lib/bff";

export async function POST(req: NextRequest): Promise<Response> {
  const auth = req.headers.get("authorization");
  await proxyJson("/auth/logout", { headers: auth ? { Authorization: auth } : {} });
  return new Response(null, { status: 204 });
}
