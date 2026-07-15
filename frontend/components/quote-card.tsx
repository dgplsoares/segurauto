"use client";

import { FileText, Percent, ShieldCheck } from "lucide-react";

import type { QuoteCard as Quote } from "../lib/api";
import { brand } from "../content/site-content";

const COVERAGE_LABELS: Record<string, string> = {
  roubo_furto: "Roubo e furto",
  colisao: "Colisão",
  danos_a_terceiros: "Danos a terceiros",
  assistencia_24h: "Assistência 24h",
  carro_reserva: "Carro reserva",
};

export function QuoteCard({ quote }: { quote: Quote }) {
  const premium = (quote.premium_cents / 100).toLocaleString("pt-BR", {
    style: "currency",
    currency: quote.currency,
  });

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
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:brightness-110"
        >
          <FileText className="size-4" /> Baixar cotação (PDF)
        </button>
      )}
    </div>
  );
}
