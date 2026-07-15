"use client";

import { Reveal } from "../reveal";
import { iconMap } from "../../lib/icons";
import { mission } from "../../content/site-content";

export function V2Mission() {
  return (
    <section className="bg-surface-cream py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-4xl font-semibold leading-tight text-primary sm:text-5xl">
            {mission.title.split("\n").map((line, i) => (
              <span key={i} className="block">
                {line}
              </span>
            ))}
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
            {mission.subtitle}
          </p>
        </Reveal>

        <div className="mt-14 grid gap-8 md:grid-cols-3">
          {mission.pillars.map((p, i) => {
            const Icon = iconMap[p.icon] ?? iconMap.ShieldCheck;
            return (
              <Reveal key={p.id} delay={i * 0.1} className="text-center">
                <div className="mx-auto flex size-16 items-center justify-center rounded-full border-2 border-primary/15 bg-background text-accent">
                  <Icon className="size-7" strokeWidth={1.75} />
                </div>
                <h3 className="mt-5 font-display text-2xl font-semibold text-primary">
                  {p.title}
                </h3>
                <p className="mx-auto mt-3 max-w-xs text-muted-foreground">
                  {p.description}
                </p>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
