/**
 * Orquestra a máquina de estados do fluxo prompt-first:
 *   idle → presignup → otp → chat
 * Guarda o prompt inicial, os dados do lead e o TOKEN DE SESSÃO apenas em
 * memória (React state) — sem cookie/localStorage (decisão de integração
 * posterior). É a única cola entre a UI e a camada de dados (lib/api.ts).
 */

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { createLead, requestOtp, verifyOtp, type LeadPayload } from "./api";
import { track } from "./analytics";
import { pickCampaign } from "./utm";

export type FlowStep = "idle" | "presignup" | "otp" | "chat";
export type FlowMode = "signup" | "login";

interface LeadFlowContextValue {
  step: FlowStep;
  mode: FlowMode;
  initialPrompt: string;
  email: string;
  token: string | null;
  /** Abre o fluxo de cadastro a partir de um prompt do hero/reconversão. */
  startWithPrompt: (prompt: string) => void;
  /** Abre o fluxo de login (já tem cadastro) — pede só o e-mail antes do OTP. */
  startLogin: () => void;
  /** Modal 1: envia o lead (createLead) e dispara o OTP (requestOtp). */
  submitLead: (data: Omit<LeadPayload, "zipcode" | "source">) => Promise<void>;
  /** Login: dispara o OTP apenas com o e-mail. */
  submitLoginEmail: (email: string) => Promise<void>;
  /** Modal 2: verifica o código e, se válido, abre o chat. */
  verify: (code: string) => Promise<void>;
  /** Reenvia o código para o e-mail atual. */
  resendOtp: () => Promise<void>;
  /** Fecha os modais e volta ao estado ocioso (mantém o chat se autenticado). */
  close: () => void;
}

const LeadFlowContext = createContext<LeadFlowContextValue | null>(null);

export function LeadFlowProvider({ children }: { children: ReactNode }) {
  const [step, setStep] = useState<FlowStep>("idle");
  const [mode, setMode] = useState<FlowMode>("signup");
  const [initialPrompt, setInitialPrompt] = useState("");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState<string | null>(null);

  const value = useMemo<LeadFlowContextValue>(() => {
    return {
      step,
      mode,
      initialPrompt,
      email,
      token,

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
        // `source` = plataforma do UTM sorteado (meta|google) — atribuição de campanha.
        await createLead({ ...data, zipcode: "00000-000", source: campaign.platform });
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
        track("otp_verified");
        setStep("chat");
      },

      async resendOtp() {
        await requestOtp(email);
      },

      close() {
        setStep("idle");
      },
    };
  }, [step, mode, initialPrompt, email, token]);

  return <LeadFlowContext.Provider value={value}>{children}</LeadFlowContext.Provider>;
}

export function useLeadFlow() {
  const ctx = useContext(LeadFlowContext);
  if (!ctx) throw new Error("useLeadFlow deve ser usado dentro de <LeadFlowProvider>");
  return ctx;
}
