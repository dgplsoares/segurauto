"use client";

import { motion } from "motion/react";
import { Star, Check } from "lucide-react";
import { PromptBox } from "../prompt-box";
import { IllustrationDriver } from "../illustrations/driver";
import { IllustrationCar } from "../illustrations/car";
import { useLeadFlow } from "../../lib/lead-flow-context";
import { heroV2 } from "../../content/site-content";

export function V2Hero() {
  const { startWithPrompt, startLogin } = useLeadFlow();

  return (
    <section className="relative overflow-hidden bg-background">
      <div className="mx-auto max-w-3xl px-4 pt-16 text-center sm:px-6 sm:pt-24">
        <motion.span
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-sm text-primary"
        >
          <span className="size-2 rounded-full bg-accent" />
          {heroV2.eyebrow}
        </motion.span>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05 }}
          className="mx-auto mt-6 max-w-2xl font-display text-5xl font-semibold leading-[1.05] tracking-tight text-primary sm:text-6xl"
        >
          {heroV2.headline.split("\n").map((line, i) => (
            <span key={i} className="block">
              {line}
            </span>
          ))}
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.12 }}
          className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground"
        >
          {heroV2.subheadline}
        </motion.p>

        {/* Campo de prompt — ação primária */}
        <motion.div
          id="hero-prompt"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mx-auto mt-8 max-w-xl scroll-mt-24 text-left"
        >
          <PromptBox onSubmit={startWithPrompt} />
          <div className="mt-3 flex items-center justify-center">
            <button
              type="button"
              onClick={startLogin}
              className="text-sm text-muted-foreground underline underline-offset-4 transition-colors hover:text-primary"
            >
              Já tem cadastro? Entre
            </button>
          </div>
        </motion.div>

        {/* Avaliação */}
        <div className="mt-6 flex items-center justify-center gap-2 text-sm">
          <span className="flex gap-0.5">
            {[0, 1, 2, 3, 4].map((i) => (
              <Star key={i} className="size-4 fill-accent text-accent" />
            ))}
          </span>
          <span className="text-muted-foreground">{heroV2.ratingLabel}</span>
        </div>

        {/* Selos */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
          {heroV2.badges.map((b) => (
            <span key={b} className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Check className="size-4 text-accent" /> {b}
            </span>
          ))}
        </div>
      </div>

      {/* Faixa creme com ilustrações line-art */}
      <div className="relative mt-12">
        <div className="relative bg-surface-cream pt-10">
          <div className="mx-auto flex max-w-6xl items-end justify-between px-4 sm:px-6">
            <IllustrationDriver className="h-28 w-36 text-primary sm:h-40 sm:w-52" />
            <IllustrationCar className="h-24 w-40 text-primary sm:h-32 sm:w-56" />
          </div>
          {/* onda inferior separando da próxima seção creme (mesma cor: continua) */}
        </div>
      </div>
    </section>
  );
}
