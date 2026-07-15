"use client";

import { Star } from "lucide-react";
import { Reveal } from "../reveal";
import { PromptBox } from "../prompt-box";
import { useLeadFlow } from "../../lib/lead-flow-context";
import { reconversion, heroV2 } from "../../content/site-content";

export function V2Reconversion() {
  const { startWithPrompt, startLogin } = useLeadFlow();

  return (
    <section className="bg-surface-cream py-20 sm:py-28">
      <div className="mx-auto max-w-2xl px-4 text-center sm:px-6">
        <Reveal>
          <h2 className="font-display text-4xl font-semibold leading-tight text-primary sm:text-5xl">
            {reconversion.title}
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
            {reconversion.subtitle}
          </p>
        </Reveal>

        <Reveal delay={0.1} className="mx-auto mt-8 max-w-xl text-left">
          <PromptBox onSubmit={startWithPrompt} />
          <div className="mt-3 text-center">
            <button
              type="button"
              onClick={startLogin}
              className="text-sm text-muted-foreground underline underline-offset-4 transition-colors hover:text-primary"
            >
              Já tem cadastro? Entre
            </button>
          </div>
        </Reveal>

        <div className="mt-6 flex items-center justify-center gap-2 text-sm">
          <span className="flex gap-0.5">
            {[0, 1, 2, 3, 4].map((i) => (
              <Star key={i} className="size-4 fill-accent text-accent" />
            ))}
          </span>
          <span className="text-muted-foreground">{heroV2.ratingLabel}</span>
        </div>
      </div>
    </section>
  );
}
