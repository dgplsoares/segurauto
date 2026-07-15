// POST /api/auth/verify-otp → POST /auth/verify-otp (ai-service). 200 {token} | 401.
import type { NextRequest } from "next/server";

import { proxyJson } from "@/lib/bff";

export async function POST(req: NextRequest): Promise<Response> {
  const body = await req.json();
  return proxyJson("/auth/verify-otp", { body });
}
