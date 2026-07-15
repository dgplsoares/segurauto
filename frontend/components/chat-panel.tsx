"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Bot, UserRound, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { Button } from "./ui/button";
import { ChatBubble, TypingBubble, type ChatMessage } from "./chat-bubble";
import { useLeadFlow } from "../lib/lead-flow-context";
import { sendChatMessage } from "../lib/api";
import { track } from "../lib/analytics";
import { brand } from "../content/site-content";

let idSeq = 0;
const nextId = () => `msg_${idSeq++}`;

export function ChatPanel() {
  const { step, initialPrompt, token, close } = useLeadFlow();
  const open = step === "chat";

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [typing, setTyping] = useState(false);
  const [input, setInput] = useState("");
  const [handoff, setHandoff] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);

  // Ao abrir, semeia a conversa com o prompt do hero como 1ª mensagem.
  useEffect(() => {
    if (open && !startedRef.current) {
      startedRef.current = true;
      const firstText = initialPrompt || "Olá! Quero cotar meu seguro de auto.";
      setMessages([{ id: nextId(), role: "user", text: firstText }]);
      void respond(firstText);
    }
    if (!open) {
      startedRef.current = false;
      setMessages([]);
      setHandoff(false);
      setInput("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  const respond = async (text: string) => {
    setTyping(true);
    try {
      const res = await sendChatMessage(text, token ?? "");
      setMessages((m) => [...m, { id: nextId(), role: "assistant", text: res.answer }]);
      setHandoff(res.handoff_suggested);
    } finally {
      setTyping(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || typing) return;
    track("chat_message", { length: text.length });
    setMessages((m) => [...m, { id: nextId(), role: "user", text }]);
    setInput("");
    await respond(text);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-stretch justify-center bg-primary/20 backdrop-blur-sm sm:items-center sm:p-4"
        >
          <motion.div
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 30, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 28 }}
            className="flex h-full w-full max-w-2xl flex-col overflow-hidden bg-background shadow-2xl sm:h-[82vh] sm:rounded-3xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between gap-3 border-b bg-primary px-5 py-4 text-primary-foreground">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-full bg-accent text-accent-foreground">
                  <Bot className="size-5" />
                </div>
                <div>
                  <p className="font-medium leading-tight">Consultor {brand.name}</p>
                  <p className="flex items-center gap-1.5 text-xs text-primary-foreground/70">
                    <span className="size-2 rounded-full bg-accent" /> Online agora
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={close}
                aria-label="Fechar chat"
                className="text-primary-foreground hover:bg-white/10 hover:text-primary-foreground"
              >
                <X />
              </Button>
            </div>

            {/* Mensagens */}
            <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto bg-muted/40 px-4 py-5">
              {messages.map((m) => (
                <ChatBubble key={m.id} message={m} />
              ))}
              {typing && <TypingBubble />}

              {handoff && !typing && (
                <div className="flex flex-wrap gap-2 pl-10">
                  <Button
                    size="sm"
                    onClick={() => {
                      setMessages((m) => [
                        ...m,
                        {
                          id: nextId(),
                          role: "assistant",
                          text: "Perfeito! Um corretor da SegurAuto vai continuar seu atendimento em instantes. 👌",
                        },
                      ]);
                      setHandoff(false);
                    }}
                    className="rounded-full bg-accent text-accent-foreground hover:brightness-105"
                  >
                    <UserRound className="size-4" /> Falar com um corretor
                  </Button>
                </div>
              )}
            </div>

            {/* Input */}
            <div className="border-t bg-background p-3">
              <div className="flex items-end gap-2 rounded-2xl border bg-input-background p-1.5 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/25">
                <textarea
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void handleSend();
                    }
                  }}
                  placeholder="Escreva sua mensagem…"
                  aria-label="Escreva sua mensagem"
                  className="max-h-28 flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none"
                />
                <button
                  type="button"
                  onClick={() => void handleSend()}
                  disabled={!input.trim() || typing}
                  aria-label="Enviar"
                  className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground transition disabled:opacity-40"
                >
                  <ArrowUp className="size-4" />
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
