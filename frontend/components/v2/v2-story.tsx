"use client";

import { ArrowRight } from "lucide-react";
import { Reveal } from "../reveal";
import { IllustrationMascot } from "../illustrations/mascot";
import { story } from "../../content/site-content";

export function V2Story() {
  return (
    <section className="bg-background py-20 sm:py-28">
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
        <Reveal>
          <IllustrationMascot className="mx-auto h-32 w-auto text-primary" />
        </Reveal>
        <Reveal delay={0.1}>
          <h2 className="mt-6 font-display text-4xl font-semibold leading-tight text-primary sm:text-5xl">
            {story.title}
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
            {story.text}
          </p>
          <a
            href="#"
            className="mt-7 inline-flex items-center gap-2 font-medium text-accent underline-offset-4 hover:underline"
          >
            {story.cta}
            <ArrowRight className="size-4" />
          </a>
        </Reveal>
      </div>
    </section>
  );
}
