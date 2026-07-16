/**
 * Orquestra a máquina de estados do fluxo prompt-first:
 *   idle → presignup → otp → chat
 * Guarda o prompt inicial, os dados do lead e o TOKEN DE SESSÃO. O token é PERSISTIDO em localStorage
 * (item 3.1): sobrevive a hard reload E ao fechar/reabrir a aba. O backend é a autoridade (guarda só o
 * sha256 do token, revogável; janela idle de 30min deslizante + teto absoluto de 12h). No mount, o token
 * guardado é revalidado (`GET /auth/session`) antes de renderizar a UI autenticada. É a única cola entre a
 * UI e a camada de dados (lib/api.ts).
 */
"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  createLead,
  logout as apiLogout,
  requestOtp,
  validateSession,
  verifyOtp,
  type LeadPayload,
} from "./api";
import { track } from "./analytics";
import { pickCampaign, readClickId } from "./utm";

export type FlowStep = "idle" | "presignup" | "otp" | "chat";
export type FlowMode = "signup" | "login";

// Persistência da sessão (item 3.1). localStorage (não sessionStorage, que morre no fechar da aba).
const STORAGE_KEY = "segurauto.session";
const ABSOLUTE_TTL_MS = 12 * 60 * 60 * 1000; // espelha session_absolute_ttl_s (43200s) — teto local sem rede

interface StoredSession {
  token: string;
  issuedAt: number;
}

function readStored(): StoredSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    return parsed?.token && typeof parsed.issuedAt === "number" ? parsed : null;
  } catch {
    return null;
  }
}

function writeStored(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, issuedAt: Date.now() }));
  } catch {
    /* quota/modo privado — segue só em memória nesta aba */
  }
}

function clearStored(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

interface LeadFlowContextValue {
  step: FlowStep;
  mode: FlowMode;
  initialPrompt: string;
  email: string;
  token: string | null;
  /** false enquanto a sessão persistida ainda é validada no mount — evita o flash Entrar↔Sair. */
  authReady: boolean;
  /** Abre o fluxo de cadastro a partir de um prompt do hero/reconversão. */
  startWithPrompt: (prompt: string) => void;
  /** Abre o fluxo de login (já tem cadastro) — pede só o e-mail antes do OTP. */
  startLogin: () => void;
  /** Modal 1: envia o lead (createLead) e dispara o OTP (requestOtp). */
  submitLead: (data: Omit<LeadPayload, "zipcode" | "source">) => Promise<void>;
  /** Login: dispara o OTP apenas com o e-mail. */
  submitLoginEmail: (email: string) => Promise<void>;
  /** Modal 2: verifica o código e, se válido, abre o chat (e persiste a sessão). */
  verify: (code: string) => Promise<void>;
  /** Reenvia o código para o e-mail atual. */
  resendOtp: () => Promise<void>;
  /** Fecha os modais e volta ao estado ocioso (mantém a sessão se autenticado). */
  close: () => void;
  /** Autenticado: abre o modal com a conversa EM ANDAMENTO (resume, sem novo prompt) — item 3.2. */
  openChat: () => void;
  /** Encerra a sessão: revoga no servidor + limpa o localStorage + volta a "não autenticado" — item 3.2. */
  logout: () => Promise<void>;
  /** Limpa a sessão sem chamar o servidor (ex.: um 401 num call autenticado revelou token morto/expirado). */
  clearSession: () => void;
}

const LeadFlowContext = createContext<LeadFlowContextValue | null>(null);

export function LeadFlowProvider({ children }: { children: ReactNode }) {
  const [step, setStep] = useState<FlowStep>("idle");
  const [mode, setMode] = useState<FlowMode>("signup");
  const [initialPrompt, setInitialPrompt] = useState("");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  // Click ID de campanha (gclid/fbclid) lido da URL uma vez no load da LP (F6) — atribuição de conversão.
  const [clickId] = useState<string | undefined>(() => readClickId());

  // Rehidratação (item 3.1): lê o token do localStorage no MOUNT (não no initializer → evita mismatch de
  // hidratação SSR). Descarta > 12h (teto absoluto) sem rede; senão valida no backend antes de confiar.
  useEffect(() => {
    const stored = readStored();
    if (!stored) {
      setAuthReady(true);
      return;
    }
    if (Date.now() - stored.issuedAt >= ABSOLUTE_TTL_MS) {
      clearStored();
      setAuthReady(true);
      return;
    }
    let alive = true;
    void validateSession(stored.token).then((state) => {
      if (!alive) return;
      // Só apaga num 401 DEFINITIVO (sessão morta). Num 5xx/rede (outage transitório, ex.: ai-service
      // reiniciando num deploy) mantém o token — o clear-on-401 num call autenticado é o backstop.
      if (state === "invalid") clearStored();
      else setToken(stored.token);
      setAuthReady(true);
    });
    return () => {
      alive = false;
    };
  }, []);

  const value = useMemo<LeadFlowContextValue>(() => {
    return {
      step,
      mode,
      initialPrompt,
      email,
      token,
      authReady,

      startWithPrompt(prompt: string) {
        track("prompt_submit", { length: prompt.length });
        setInitialPrompt(prompt.trim());
        setMode("signup");
        // Se já autenticado, vai direto ao chat.
        if (token) {
          setStep("chat");
        } else {
          track("signup_view");
          setStep("presignup");
        }
      },

      startLogin() {
        setMode("login");
        setEmail("");
        track("otp_view", { mode: "login" });
        setStep("otp");
      },

      async submitLead(data) {
        const campaign = pickCampaign(); // sorteio de UTM POR SUBMISSÃO (F5c.2)
        track("signup_submit", { campaign: campaign.campaign });
        // `source` = plataforma do UTM sorteado (meta|google); `click_id` = gclid/fbclid da URL (F6).
        await createLead({ ...data, zipcode: "00000-000", source: campaign.platform, click_id: clickId });
        setEmail(data.email);
        await requestOtp(data.email);
        track("otp_view", { mode: "signup" });
        setStep("otp");
      },

      async submitLoginEmail(loginEmail: string) {
        setEmail(loginEmail);
        await requestOtp(loginEmail);
      },

      async verify(code: string) {
        const result = await verifyOtp(email, code);
        setToken(result.token);
        writeStored(result.token); // persiste a sessão (item 3.1)
        track("otp_verified");
        setStep("chat");
      },

      async resendOtp() {
        await requestOtp(email);
      },

      close() {
        setStep("idle");
      },

      openChat() {
        // Resume puro: abre o modal sem tocar no initialPrompt → o ChatPanel reabre a conversa existente
        // (não anexa mensagem). Distinto de startWithPrompt, que enviaria um novo prompt.
        setStep("chat");
      },

      async logout() {
        const current = token;
        setToken(null);
        clearStored();
        setStep("idle");
        setEmail("");
        setInitialPrompt("");
        if (current) await apiLogout(current); // revoga no servidor (best-effort)
      },

      clearSession() {
        setToken(null);
        clearStored();
      },
    };
  }, [step, mode, initialPrompt, email, token, authReady, clickId]);

  return <LeadFlowContext.Provider value={value}>{children}</LeadFlowContext.Provider>;
}

export function useLeadFlow() {
  const ctx = useContext(LeadFlowContext);
  if (!ctx) throw new Error("useLeadFlow deve ser usado dentro de <LeadFlowProvider>");
  return ctx;
}
