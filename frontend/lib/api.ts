/**
 * Camada de dados do frontend (client-side) — ÚNICO ponto que fala com o BFF (/api/*).
 * O contrato (assinaturas + tipos) segue o protótipo do frontend; aqui os corpos fazem `fetch` REAL.
 * Na reconciliação, os componentes portados consomem estas funções sem mudança.
 * (Server-side, quem fala com o ai-service é lib/bff.ts, usado pelos route handlers.)
 */

export interface LeadPayload {
  name: string;
  email: string;
  phone: string;
  vehicle: string;
  zipcode: string; // coletado na conversa; enviado provisório pelo modal
  consent: boolean;
  source?: string; // atribuição de campanha/UTM
  click_id?: string; // gclid/fbclid capturado da URL da LP (F6)
}

export interface LeadResult {
  id: string;
  status: string;
  deduped: boolean;
}

export interface VerifyOtpResult {
  token: string;
  expires_in: number;
}

export interface ChatResult {
  answer: string;
  handoff_suggested: boolean;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

function newIdempotencyKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}`;
}

/** POST /api/lead — header Idempotency-Key. Sucesso 201; retry mesma key = 200 (deduped). */
export async function createLead(payload: LeadPayload): Promise<LeadResult> {
  const res = await fetch("/api/lead", {
    method: "POST",
    headers: { "content-type": "application/json", "Idempotency-Key": newIdempotencyKey() },
    body: JSON.stringify(payload),
  });
  if (res.status !== 201 && res.status !== 200) {
    throw new ApiError(res.status, "Não foi possível registrar seus dados. Tente novamente.");
  }
  return (await res.json()) as LeadResult;
}

/** POST /api/auth/request-otp — sempre 202 (neutro; não revela se o e-mail existe). */
export async function requestOtp(email: string): Promise<{ status: 202 }> {
  await fetch("/api/auth/request-otp", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email }),
  });
  return { status: 202 };
}

/** POST /api/auth/verify-otp — { token, expires_in } | ApiError(401). */
export async function verifyOtp(email: string, code: string): Promise<VerifyOtpResult> {
  const res = await fetch("/api/auth/verify-otp", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (res.status === 401) throw new ApiError(401, "Código inválido ou expirado.");
  if (!res.ok) throw new ApiError(res.status, "Falha ao verificar o código.");
  return (await res.json()) as VerifyOtpResult;
}

/** Estado da sessão persistida: valid (200) | invalid (401 definitivo) | unknown (5xx/rede — outage). */
export type SessionState = "valid" | "invalid" | "unknown";

/** GET /api/auth/session — distingue sessão MORTA (401) de falha TRANSITÓRIA (5xx/rede). A rehidratação só
 * deve apagar o token guardado num 401 definitivo, nunca num blip de rede/deploy (senão o usuário perde uma
 * sessão ainda válida ao dar reload enquanto o ai-service reinicia). */
export async function validateSession(token: string): Promise<SessionState> {
  try {
    const res = await fetch("/api/auth/session", { headers: { Authorization: `Bearer ${token}` } });
    if (res.ok) return "valid";
    if (res.status === 401) return "invalid";
    return "unknown"; // 5xx/502 (ai-service reiniciando num deploy) — NÃO é uma sessão morta
  } catch {
    return "unknown"; // offline/rede indisponível — não apaga o token
  }
}

/** POST /api/auth/logout — revoga a sessão no servidor. Best-effort (não lança). */
export async function logout(token: string): Promise<void> {
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    // ignora — o cliente limpa o estado local de qualquer forma
  }
}

/** POST /api/support — header Authorization: Bearer. Retorna { answer, handoff_suggested }. */
export async function sendChatMessage(message: string, token: string): Promise<ChatResult> {
  const res = await fetch("/api/support", {
    method: "POST",
    headers: { "content-type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new ApiError(res.status, "Falha ao falar com o consultor.");
  return (await res.json()) as ChatResult;
}

// --- Conversa de cotação MULTI-TURN (F5c.2) ---------------------------------

export interface QuoteCard {
  quote_id: string;
  premium_cents: number;
  currency: string;
  coverages: string[];
  broker_applied: boolean;
  pdf_ref: string | null;
}

export interface TurnResult {
  reply: string;
  slots: Record<string, unknown>;
  missing_slots: string[];
  ready_to_quote: boolean;
  handoff_suggested: boolean;
  quote: QuoteCard | null;
}

/** POST /api/support/sessions — cria a sessão de conversa de cotação (multi-turn). */
export async function createChatSession(token: string): Promise<{ session_id: string }> {
  const res = await fetch("/api/support/sessions", {
    method: "POST",
    headers: { "content-type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new ApiError(res.status, "Não foi possível iniciar a conversa.");
  return (await res.json()) as { session_id: string };
}

/** POST /api/support/sessions/{id}/messages — um turno; devolve reply + card quando os slots completam. */
export async function sendTurn(sessionId: string, message: string, token: string): Promise<TurnResult> {
  const res = await fetch(`/api/support/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: "POST",
    headers: { "content-type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message, client_turn_id: newIdempotencyKey() }),
  });
  if (!res.ok) throw new ApiError(res.status, "Falha ao enviar a mensagem.");
  return (await res.json()) as TurnResult;
}

// --- Confirmação → ações write-through-outbox (F6) --------------------------

export type ConfirmAction = "contract" | "handoff";

export interface ConfirmResult {
  session_id: string;
  action: ConfirmAction;
  status: "queued" | "already_requested"; // idempotente
  message: string;
}

/** POST /api/support/sessions/{id}/confirm — dispara as ações (contratar/handoff). Idempotente. */
export async function confirmAction(
  sessionId: string,
  action: ConfirmAction,
  token: string,
): Promise<ConfirmResult> {
  const res = await fetch(`/api/support/sessions/${encodeURIComponent(sessionId)}/confirm`, {
    method: "POST",
    headers: { "content-type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new ApiError(res.status, "Não foi possível concluir agora.");
  return (await res.json()) as ConfirmResult;
}
