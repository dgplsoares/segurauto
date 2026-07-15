"use client";

import { useState } from "react";
import { Check, FileText, Loader2, Percent, ShieldCheck, UserRound } from "lucide-react";

import { confirmAction, type ConfirmAction, type QuoteCard as Quote } from "../lib/api";
import { track } from "../lib/analytics";
import { brand } from "../content/site-content";

const COVERAGE_LABELS: Record<string, string> = {
  roubo_furto: "Roubo e furto",
  colisao: "Colisão",
  danos_a_terceiros: "Danos a terceiros",
  assistencia_24h: "Assistência 24h",
  carro_reserva: "Carro reserva",
};

export function QuoteCard({ quote, sessionId, token }: { quote: Quote; sessionId?: string; token?: string }) {
  const premium = (quote.premium_cents / 100).toLocaleString("pt-BR", {
    style: "currency",
    currency: quote.currency,
  });

  const [pending, setPending] = useState<ConfirmAction | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null); // mensagem do backend quando concluído
  const [error, setError] = useState(false);
  const canConfirm = Boolean(sessionId && token);

  const run = async (action: ConfirmAction) => {
    if (!sessionId || !token || pending) return;
    setPending(action);
    setError(false);
    track("quote_confirm", { action });
    try {
      const res = await confirmAction(sessionId, action, token);
      setOutcome(res.message);
    } catch {
      setError(true);
    } finally {
      setPending(null);
    }
  };

  return (
    <div className="ml-10 rounded-2xl border border-accent/30 bg-background p-4 shadow-sm">
      <p className="text-sm font-medium text-muted-foreground">Sua cotação {brand.name}</p>
      <p className="mt-1 flex items-baseline gap-1">
        <span className="text-3xl font-semibold text-primary">{premium}</span>
        <span className="text-sm text-muted-foreground">/ano</span>
      </p>
      {quote.broker_applied && (
        <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent">
          <Percent className="size-3.5" /> desconto de corretor aplicado
        </span>
      )}
      <ul className="mt-3 grid gap-1.5">
        {quote.coverages.map((c) => (
          <li key={c} className="flex items-center gap-2 text-sm text-foreground">
            <ShieldCheck className="size-4 text-accent" /> {COVERAGE_LABELS[c] ?? c}
          </li>
        ))}
      </ul>

      {quote.pdf_ref && (
        <button
          type="button"
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-background px-4 py-2.5 text-sm font-medium text-foreground transition hover:bg-muted"
        >
          <FileText className="size-4" /> Baixar cotação (PDF)
        </button>
      )}

      {/* Confirmação → ações (F6). Some após concluído; mostra a mensagem honesta do backend. */}
      {canConfirm && outcome === null && (
        <div className="mt-3 grid gap-2">
          <button
            type="button"
            onClick={() => void run("contract")}
            disabled={pending !== null}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-accent-foreground transition hover:brightness-105 disabled:opacity-50"
          >
            {pending === "contract" ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
            Quero contratar
          </button>
          <button
            type="button"
            onClick={() => void run("handoff")}
            disabled={pending !== null}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-background px-4 py-2.5 text-sm font-medium text-foreground transition hover:bg-muted disabled:opacity-50"
          >
            {pending === "handoff" ? <Loader2 className="size-4 animate-spin" /> : <UserRound className="size-4" />}
            Falar com um corretor
          </button>
          {error && (
            <p className="text-xs text-destructive">Não foi possível concluir agora. Tente novamente.</p>
          )}
        </div>
      )}

      {outcome !== null && (
        <div className="mt-3 flex items-start gap-2 rounded-xl bg-accent/10 p-3 text-sm text-foreground">
          <Check className="mt-0.5 size-4 shrink-0 text-accent" />
          <span>{outcome}</span>
        </div>
      )}
    </div>
  );
}
