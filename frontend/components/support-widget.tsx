"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Bot, MessageCircle, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { ChatBubble, TypingBubble, type ChatMessage } from "./chat-bubble";
import { sendChatMessage } from "../lib/api";
import { brand } from "../content/site-content";

let sid = 0;
const nid = () => `sup_${sid++}`;

/** Chat de IA flutuante (suporte). Single-turn mockado, não-bloqueante. */
export function SupportWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: nid(),
      role: "assistant",
      text: `Oi! Sou o assistente da ${brand.name}. Posso tirar dúvidas sobre coberturas, assistência 24h e como cotar. Como posso ajudar?`,
    },
  ]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing, open]);

  const send = async () => {
    const text = input.trim();
    if (!text || typing) return;
    setMessages((m) => [...m, { id: nid(), role: "user", text }]);
    setInput("");
    setTyping(true);
    try {
      const res = await sendChatMessage(text, "");
      setMessages((m) => [...m, { id: nid(), role: "assistant", text: res.answer }]);
    } finally {
      setTyping(false);
    }
  };

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.96 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-24 right-4 z-40 flex h-[70vh] max-h-[520px] w-[calc(100vw-2rem)] max-w-sm flex-col overflow-hidden rounded-3xl border bg-background shadow-2xl sm:right-6"
          >
            <div className="flex items-center justify-between bg-primary px-4 py-3 text-primary-foreground">
              <div className="flex items-center gap-2.5">
                <div className="flex size-8 items-center justify-center rounded-full bg-accent text-accent-foreground">
                  <Bot className="size-4" />
                </div>
                <p className="font-medium">Suporte {brand.name}</p>
              </div>
              <button onClick={() => setOpen(false)} aria-label="Fechar suporte" className="opacity-80 hover:opacity-100">
                <X className="size-5" />
              </button>
            </div>

            <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto bg-muted/40 px-3 py-4">
              {messages.map((m) => (
                <ChatBubble key={m.id} message={m} />
              ))}
              {typing && <TypingBubble />}
            </div>

            <div className="border-t p-2.5">
              <div className="flex items-center gap-2 rounded-2xl border bg-input-background p-1 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/25">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="Escreva sua dúvida…"
                  aria-label="Escreva sua dúvida"
                  className="flex-1 bg-transparent px-3 py-1.5 text-sm outline-none"
                />
                <button
                  onClick={send}
                  disabled={!input.trim() || typing}
                  aria-label="Enviar"
                  className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground disabled:opacity-40"
                >
                  <ArrowUp className="size-4" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Fechar suporte" : "Abrir suporte"}
        className="fixed bottom-5 right-4 z-40 flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-xl transition hover:scale-105 active:scale-95 sm:right-6"
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={open ? "x" : "chat"}
            initial={{ rotate: -90, opacity: 0 }}
            animate={{ rotate: 0, opacity: 1 }}
            exit={{ rotate: 90, opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            {open ? <X className="size-6" /> : <MessageCircle className="size-6" />}
          </motion.span>
        </AnimatePresence>
      </button>
    </>
  );
}
