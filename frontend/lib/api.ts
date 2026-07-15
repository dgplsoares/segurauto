// Camada de dados do frontend (client-side). É o ÚNICO ponto que fala com o BFF (/api/*).
// A UI — inclusive o export do Figma Make — deve chamar SÓ estas funções. Na reconciliação,
// troca-se o módulo mock do design por este arquivo (mesmas assinaturas → integração 1:1).
// (Server-side, quem fala com o ai-service é lib/bff.ts, usado pelos route handlers.)

export type LeadInput = {
  name: string;
  email: string;
  phone: string;
  vehicle: string;
  zipcode: string;
  consent: boolean;
  source?: string;
};

export type LeadResult = { id: string; status: string; deduped: boolean };
export type Session = { token: string; expiresIn: number };
export type ChatReply = { answer: string; handoffSuggested: boolean };

/** Erro de API com o status HTTP do BFF, para a UI ramificar (ex.: 401 no OTP). */
export class ApiError extends Error {
  constructor(public code: string, public status: number) {
    super(code);
    this.name = "ApiError";
  }
}

function newIdempotencyKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now());
}

/**
 * Cria (ou deduplica) o lead. `idempotencyKey` deve ser ESTÁVEL entre retentativas da mesma
 * submissão (gere uma vez ao abrir o modal); se omitido, gera uma nova. Sucesso: 201 (novo) ou
 * 200 (dedup do dono). Lança `ApiError` em 409 (colisão de key com outra identidade) ou erro.
 */
export async function createLead(input: LeadInput, idempotencyKey?: string): Promise<LeadResult> {
  const res = await fetch("/api/lead", {
    method: "POST",
    headers: { "content-type": "application/json", "Idempotency-Key": idempotencyKey ?? newIdempotencyKey() },
    body: JSON.stringify(input),
  });
  if (res.status !== 201 && res.status !== 200) throw new ApiError("lead_failed", res.status);
  return (await res.json()) as LeadResult;
}

/** Solicita o código OTP. Resposta 202 SEMPRE (neutra) — não revela se o e-mail existe. */
export async function requestOtp(email: string): Promise<void> {
  await fetch("/api/auth/request-otp", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

/** Verifica o OTP e devolve a sessão. Lança `ApiError(status=401)` se o código for inválido/expirado. */
export async function verifyOtp(email: string, code: string): Promise<Session> {
  const res = await fetch("/api/auth/verify-otp", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (res.status === 401) throw new ApiError("invalid_or_expired_otp", 401);
  if (!res.ok) throw new ApiError("verify_failed", res.status);
  const data = (await res.json()) as { token: string; expires_in: number };
  return { token: data.token, expiresIn: data.expires_in };
}

/** Envia uma mensagem ao consultor de IA (requer sessão). Lança `ApiError` em falha. */
export async function sendChatMessage(message: string, token: string): Promise<ChatReply> {
  const res = await fetch("/api/support", {
    method: "POST",
    headers: { "content-type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new ApiError("chat_failed", res.status);
  const data = (await res.json()) as { answer: string; handoff_suggested: boolean };
  return { answer: data.answer, handoffSuggested: data.handoff_suggested };
}
