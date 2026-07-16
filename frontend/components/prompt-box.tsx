"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "./ui/utils";
import { track } from "../lib/analytics";
import { hero } from "../content/site-content";

interface PromptBoxProps {
  onSubmit: (value: string) => void;
  /** Variante visual: hero (grande, sobre fundo claro) ou reconversão. */
  autoFocus?: boolean;
  className?: string;
}

/**
 * Campo de prompt central — a ação primária da LP.
 * Placeholder animado que alterna exemplos, Enter envia, cursor pulsando.
 */
export function PromptBox({ onSubmit, autoFocus, className }: PromptBoxProps) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const [exampleIndex, setExampleIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Alterna os exemplos do placeholder enquanto o campo está vazio e sem foco.
  useEffect(() => {
    if (value || focused) return;
    const id = setInterval(() => {
      setExampleIndex((i) => (i + 1) % hero.promptExamples.length);
    }, 3000);
    return () => clearInterval(id);
  }, [value, focused]);

  // Auto-resize do textarea.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed) {
      textareaRef.current?.focus();
      return;
    }
    onSubmit(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const showPlaceholder = !value;

  return (
    <div
      onMouseDown={(e) => {
        // Toda a área do contorno (gradiente) foca o campo — o alvo de clique é grande, mas o textarea é
        // pequeno. Exceto: clique no botão (faz só a ação dele) ou no próprio textarea (deixa o caret nativo).
        if ((e.target as HTMLElement).closest("button, textarea")) return;
        e.preventDefault(); // evita perder o foco/deseleção ao clicar na área "morta"
        textareaRef.current?.focus();
      }}
      className={cn(
        "group relative flex w-full cursor-text flex-col justify-between gap-2 rounded-[20px] border-[3px] border-transparent px-4 py-3.5 transition-all duration-300",
        "shadow-[0px_8px_5px_rgba(0,0,0,0.1),0px_20px_12.5px_rgba(0,0,0,0.1)]",
        focused && "ring-4 ring-accent/25",
        className,
      )}
      style={{
        background: `linear-gradient(var(--card), var(--card)) padding-box, linear-gradient(135deg, rgba(251,90,90,${
          focused ? 1 : 0.4
        }) 0%, rgba(214,36,159,${focused ? 1 : 0.4}) 50%, rgba(15,61,59,${
          focused ? 1 : 0.4
        }) 100%) border-box`,
      }}
    >
      <div className="flex items-start gap-2">
        <div className="flex items-center pt-1.5 pl-1 text-accent">
          <Sparkles className="size-5 shrink-0" aria-hidden />
        </div>

        <div className="relative flex-1 py-1.5">
          {/* Placeholder animado (visível só quando vazio) */}
          {showPlaceholder && (
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 flex items-center px-1 text-muted-foreground"
            >
              <AnimatePresence mode="wait">
                <motion.span
                  key={exampleIndex}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.35 }}
                  className="truncate"
                >
                  {hero.promptExamples[exampleIndex]}
                </motion.span>
              </AnimatePresence>
              {/* cursor pulsando */}
              <span className="ml-0.5 inline-block h-5 w-px animate-pulse bg-accent opacity-95" />
            </div>
          )}

          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              setFocused(true);
              track("prompt_focus");
            }}
            onBlur={() => setFocused(false)}
            autoFocus={autoFocus}
            aria-label="Escreva sua pergunta para o consultor de IA"
            className="relative w-full resize-none bg-transparent px-1 text-foreground outline-none placeholder:text-transparent"
          />
        </div>
      </div>

      {/* Botão de envio no canto inferior direito (petróleo) */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSubmit}
          aria-label="Enviar mensagem"
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground transition-all duration-200",
            value.trim() ? "opacity-100 hover:brightness-110 active:scale-95" : "opacity-65",
          )}
        >
          <ArrowUp className="size-5" />
        </button>
      </div>
    </div>
  );
}
