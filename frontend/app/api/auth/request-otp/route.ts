// POST /api/auth/request-otp → POST /auth/request-otp (ai-service). Resposta 202 neutra.
import type { NextRequest } from "next/server";

import { proxyJson } from "@/lib/bff";

export async function POST(req: NextRequest): Promise<Response> {
  const body = await req.json();
  return proxyJson("/auth/request-otp", { body });
}
