"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import { Reveal } from "../reveal";
import { cn } from "../ui/utils";
import { iconMap } from "../../lib/icons";
import { IllustrationCar } from "../illustrations/car";
import { coverages, coverageTabsIntro } from "../../content/site-content";

export function V2CoverageTabs() {
  const [active, setActive] = useState(coverages.items[0].id);
  const current = coverages.items.find((c) => c.id === active) ?? coverages.items[0];
  const Icon = iconMap[current.icon] ?? iconMap.ShieldCheck;

  return (
    <section id="coberturas" className="bg-surface-cream py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-4xl font-semibold leading-tight text-primary sm:text-5xl">
            {coverageTabsIntro.title}
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
            {coverageTabsIntro.subtitle}
          </p>
        </Reveal>

        {/* Chips */}
        <div className="mt-10 flex snap-x gap-3 overflow-x-auto pb-2 sm:flex-wrap sm:justify-center sm:overflow-visible">
          {coverages.items.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setActive(c.id)}
              className={cn(
                "shrink-0 snap-start rounded-full border px-5 py-2.5 text-sm transition-all",
                active === c.id
                  ? "border-accent bg-accent text-accent-foreground"
                  : "border-primary/15 bg-background text-foreground hover:border-accent/50",
              )}
            >
              {c.title}
            </button>
          ))}
        </div>

        {/* Painel */}
        <div className="mt-10 grid items-center gap-10 rounded-3xl border border-border bg-background p-8 md:grid-cols-2 sm:p-12">
          <div>
            <div className="flex size-14 items-center justify-center rounded-2xl bg-secondary text-accent">
              <Icon className="size-7" strokeWidth={1.75} />
            </div>
            <h3 className="mt-5 font-display text-3xl font-semibold text-primary">
              {current.title}
            </h3>
            <p className="mt-3 max-w-md text-lg text-muted-foreground">
              {current.description}
            </p>
            <ul className="mt-6 space-y-2">
              {["Contratação em minutos", "Sem letras miúdas", "Suporte 24h"].map(
                (b) => (
                  <li key={b} className="flex items-center gap-2 text-foreground">
                    <Check className="size-5 text-accent" /> {b}
                  </li>
                ),
              )}
            </ul>
          </div>
          <div className="flex justify-center text-primary">
            <IllustrationCar className="h-40 w-full max-w-sm" />
          </div>
        </div>
      </div>
    </section>
  );
}
