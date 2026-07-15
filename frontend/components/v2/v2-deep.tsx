"use client";

import { Reveal } from "../reveal";
import { WaveDivider } from "../wave-divider";
import { IllustrationNature } from "../illustrations/nature";
import { deepSection } from "../../content/site-content";

export function V2Deep() {
  return (
    <section className="relative bg-primary text-primary-foreground">
      <div className="mx-auto max-w-4xl px-4 py-24 text-center sm:px-6 sm:py-32">
        <Reveal>
          <IllustrationNature className="mx-auto h-24 w-full max-w-md text-primary-foreground/70" />
          <span className="mt-8 inline-block rounded-full border border-primary-foreground/25 px-3 py-1 text-sm text-primary-foreground/80">
            {deepSection.eyebrow}
          </span>
          <h2 className="mx-auto mt-5 max-w-2xl font-display text-4xl font-semibold leading-tight sm:text-5xl">
            {deepSection.title}
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg text-primary-foreground/80">
            {deepSection.subtitle}
          </p>
          <button
            type="button"
            className="mt-8 rounded-full border border-primary-foreground/40 px-6 py-3 text-primary-foreground transition-colors hover:bg-primary-foreground hover:text-primary"
          >
            {deepSection.cta}
          </button>
        </Reveal>
      </div>

      {/* transição para o navy da seção de avaliações */}
      <WaveDivider className="text-surface-navy" />
    </section>
  );
}
