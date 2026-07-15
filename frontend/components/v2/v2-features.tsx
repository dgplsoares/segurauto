"use client";

import type { ReactNode } from "react";
import {
  Sparkles,
  ShieldCheck,
  FileText,
  Car,
  Check,
  ArrowUp,
} from "lucide-react";
import { Reveal } from "../reveal";
import { PhoneMockup } from "../phone-mockup";
import { Switch } from "../ui/switch";
import { features } from "../../content/site-content";

/* ---------- Telas dentro do celular ---------- */

function ChatScreen() {
  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <div className="flex size-9 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Sparkles className="size-4" />
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">Consultor SegurAuto</p>
          <p className="text-xs text-accent">online agora</p>
        </div>
      </div>
      <div className="flex-1 space-y-3">
        <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-sm text-foreground">
          Olá! Quer cotar o seguro do seu carro? 🚗
        </div>
        <div className="ml-auto max-w-[80%] rounded-2xl rounded-tr-sm bg-accent px-3 py-2 text-sm text-accent-foreground">
          Quero sim! Tenho um Onix 2021.
        </div>
        <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-sm text-foreground">
          Perfeito! Já encontrei 3 opções pra você. A partir de R$ 98/mês.
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2 rounded-full border border-border bg-input-background px-3 py-2">
        <span className="flex-1 text-sm text-muted-foreground">Escreva…</span>
        <span className="flex size-7 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <ArrowUp className="size-4" />
        </span>
      </div>
    </div>
  );
}

function PolicyScreen() {
  const items = [
    { label: "Roubo e furto", on: true },
    { label: "Colisão", on: true },
    { label: "Assistência 24h", on: true },
    { label: "Carro reserva", on: false },
  ];
  return (
    <div className="flex h-full flex-col">
      <div className="rounded-2xl bg-primary p-4 text-primary-foreground">
        <div className="flex items-center justify-between">
          <span className="text-sm opacity-80">Apólice ativa</span>
          <ShieldCheck className="size-5" />
        </div>
        <p className="mt-2 font-display text-xl font-semibold">Onix LT 2021</p>
        <p className="text-sm opacity-80">Nº 2026-0042-SA</p>
      </div>
      <div className="mt-4 flex items-center gap-2 text-sm font-medium text-foreground">
        <FileText className="size-4 text-accent" /> Coberturas
      </div>
      <div className="mt-2 space-y-2">
        {items.map((it) => (
          <div
            key={it.label}
            className="flex items-center justify-between rounded-xl border border-border px-3 py-2.5 text-sm text-foreground"
          >
            {it.label}
            <Switch defaultChecked={it.on} />
          </div>
        ))}
      </div>
    </div>
  );
}

function VehicleScreen() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Car className="size-4 text-accent" /> Seu veículo
      </div>
      <div className="mt-3 rounded-2xl border border-border p-4">
        <div className="flex h-24 items-center justify-center rounded-xl bg-muted text-muted-foreground">
          <Car className="size-12" strokeWidth={1.25} />
        </div>
        <p className="mt-3 font-display text-lg font-semibold text-foreground">
          Chevrolet Onix
        </p>
        <p className="text-sm text-muted-foreground">2021 · Flex · Placa ABC-1D23</p>
      </div>
      <div className="mt-4 space-y-2">
        {["Uso pessoal", "Garagem em casa", "Km/mês: até 1.500"].map((l) => (
          <div
            key={l}
            className="flex items-center gap-2 rounded-xl bg-secondary px-3 py-2.5 text-sm text-foreground"
          >
            <Check className="size-4 text-accent" /> {l}
          </div>
        ))}
      </div>
    </div>
  );
}

function FeesScreen() {
  const rows = [
    { label: "Seguro mensal", value: "R$ 98,00" },
    { label: "Assistência 24h", value: "Incluída" },
    { label: "Taxa de alteração", value: "R$ 0,00" },
    { label: "Taxa de administração", value: "R$ 0,00" },
  ];
  return (
    <div className="flex h-full flex-col">
      <p className="font-display text-lg font-semibold text-foreground">
        Resumo do preço
      </p>
      <p className="text-sm text-muted-foreground">Transparente, sem surpresas.</p>
      <div className="mt-4 divide-y divide-border rounded-2xl border border-border">
        {rows.map((r) => (
          <div
            key={r.label}
            className="flex items-center justify-between px-3 py-3 text-sm"
          >
            <span className="text-foreground">{r.label}</span>
            <span
              className={
                r.value === "R$ 0,00"
                  ? "font-medium text-accent"
                  : "text-foreground"
              }
            >
              {r.value}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between rounded-2xl bg-primary px-4 py-3 text-primary-foreground">
        <span>Total / mês</span>
        <span className="font-display text-xl font-semibold">R$ 98,00</span>
      </div>
    </div>
  );
}

const screens: Record<string, ReactNode> = {
  chat: <ChatScreen />,
  policy: <PolicyScreen />,
  vehicle: <VehicleScreen />,
  fees: <FeesScreen />,
};

/* ---------- Linha de feature ---------- */

function FeatureRow({
  title,
  description,
  screen,
  reverse,
}: {
  title: string;
  description: string;
  screen: ReactNode;
  reverse: boolean;
}) {
  return (
    <div className="grid items-center gap-10 md:grid-cols-2 md:gap-16">
      <Reveal className={reverse ? "md:order-2" : ""}>
        <h3 className="font-display text-3xl font-semibold leading-tight text-primary sm:text-4xl">
          {title}
        </h3>
        <p className="mt-4 max-w-md text-lg text-muted-foreground">{description}</p>
      </Reveal>
      <Reveal delay={0.1} className={reverse ? "md:order-1" : ""}>
        <PhoneMockup>{screen}</PhoneMockup>
      </Reveal>
    </div>
  );
}

export function V2Features() {
  return (
    <section id="como-funciona" className="bg-background py-20 sm:py-28">
      <div className="mx-auto flex max-w-6xl flex-col gap-20 px-4 sm:gap-28 sm:px-6">
        {features.map((f, i) => (
          <FeatureRow
            key={f.id}
            title={f.title}
            description={f.description}
            screen={screens[f.screen]}
            reverse={i % 2 === 1}
          />
        ))}
      </div>
    </section>
  );
}
