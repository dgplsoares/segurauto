"use client";

import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { Button } from "../ui/button";
import { cn } from "../ui/utils";
import { useLeadFlow } from "../../lib/lead-flow-context";
import { nav } from "../../content/site-content";

function scrollToPrompt() {
  document.getElementById("hero-prompt")?.scrollIntoView({ behavior: "smooth", block: "center" });
  document
    .querySelector<HTMLTextAreaElement>("#hero-prompt textarea")
    ?.focus({ preventScroll: true });
}

export function V2Header() {
  const { startLogin } = useLeadFlow();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-30 transition-all duration-300",
        scrolled ? "border-b border-border bg-background/90 backdrop-blur-md" : "border-b border-transparent",
      )}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <a href="#" className="font-display text-2xl font-semibold tracking-tight text-primary">
          segur<span className="text-accent">auto</span>
        </a>

        <nav className="hidden items-center gap-8 md:flex">
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm text-foreground/70 transition-colors hover:text-foreground"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button
            variant="outline"
            onClick={startLogin}
            className="rounded-full border-primary/20 text-foreground hover:bg-secondary"
          >
            Entrar
          </Button>
          <Button
            onClick={scrollToPrompt}
            className="rounded-full bg-accent text-accent-foreground hover:brightness-105"
          >
            Falar com o consultor
          </Button>
        </div>

        <button className="md:hidden" aria-label="Abrir menu" onClick={() => setOpen((o) => !o)}>
          {open ? <X /> : <Menu />}
        </button>
      </div>

      {open && (
        <div className="border-t border-border bg-background px-4 py-4 md:hidden">
          <nav className="flex flex-col gap-3">
            {nav.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="py-1 text-foreground/70"
              >
                {item.label}
              </a>
            ))}
            <div className="mt-1 flex gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setOpen(false);
                  startLogin();
                }}
                className="flex-1 rounded-full"
              >
                Entrar
              </Button>
              <Button
                onClick={() => {
                  setOpen(false);
                  scrollToPrompt();
                }}
                className="flex-1 rounded-full bg-accent text-accent-foreground"
              >
                Consultor
              </Button>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
