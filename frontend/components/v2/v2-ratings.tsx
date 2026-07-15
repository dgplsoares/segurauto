"use client";

import { Star } from "lucide-react";
import { Reveal } from "../reveal";
import { cn } from "../ui/utils";
import { ratings } from "../../content/site-content";

function StarBar({ score, highlight }: { score: number; highlight: boolean }) {
  const pct = (score / 5) * 100;
  return (
    <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-white/10">
      <div
        className={cn("h-full rounded-full", highlight ? "bg-accent" : "bg-white/40")}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function V2Ratings() {
  return (
    <section className="bg-surface-navy text-white">
      <div className="mx-auto max-w-4xl px-4 py-20 sm:px-6 sm:py-28">
        <Reveal className="text-center">
          <h2 className="font-display text-4xl font-semibold leading-tight sm:text-5xl">
            {ratings.title}
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-lg text-white/70">
            {ratings.subtitle}
          </p>
        </Reveal>

        <Reveal delay={0.1} className="mt-12">
          <p className="mb-4 text-sm text-white/60">{ratings.ratingScaleLabel}</p>
          <div className="space-y-4">
            {ratings.rows.map((row) => (
              <div
                key={row.id}
                className={cn(
                  "grid grid-cols-[7.5rem_1fr_2.5rem] items-center gap-4 rounded-2xl px-4 py-3 sm:grid-cols-[10rem_1fr_3rem]",
                  row.highlight && "bg-white/5 ring-1 ring-accent/40",
                )}
              >
                <span
                  className={cn(
                    "truncate font-medium",
                    row.highlight ? "text-accent" : "text-white/80",
                  )}
                >
                  {row.name}
                </span>
                <StarBar score={row.score} highlight={row.highlight} />
                <span className="flex items-center justify-end gap-1 text-sm tabular-nums">
                  <Star
                    className={cn(
                      "size-3.5",
                      row.highlight ? "fill-accent text-accent" : "fill-white/40 text-white/40",
                    )}
                  />
                  {row.score.toFixed(1).replace(".", ",")}
                </span>
              </div>
            ))}
          </div>
        </Reveal>

        {/* Imprensa */}
        <Reveal delay={0.15} className="mt-16 text-center">
          <p className="text-sm uppercase tracking-wider text-white/50">
            {ratings.pressLabel}
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
            {ratings.press.map((p) => (
              <span
                key={p}
                className="font-display text-xl font-semibold text-white/60"
              >
                {p}
              </span>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
