"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Bot, RotateCw, UserRound, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { Button } from "./ui/button";
import { ChatBubble, TypingBubble, type ChatMessage } from "./chat-bubble";
import { QuoteCard } from "./quote-card";
import { useLeadFlow } from "../lib/lead-flow-context";
import { ApiError, createChatSession, sendTurn, type QuoteCard as Quote } from "../lib/api";
import { track } from "../lib/analytics";
import { brand } from "../content/site-content";

let idSeq = 0;
const nextId = () => `msg_${idSeq++}`;
const DEFAULT_PROMPT = "Olá! Quero cotar meu seguro de auto.";

export function ChatPanel() {
  const { step, initialPrompt, token, close, clearSession } = useLeadFlow();
  const open = step === "chat";

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [typing, setTyping] = useState(false);
  const [input, setInput] = useState("");
  const [handoff, setHandoff] = useState(false);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [confirmedOutcome, setConfirmedOutcome] = useState<string | null>(null); // resultado da confirmação (F6)
  const [failed, setFailed] = useState(false); // criação da sessão falhou → oferece "Tentar novamente"
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionRef = useRef<string | null>(null);
  const genRef = useRef(0); // geração: invalida continuações de aberturas anteriores (corrida abrir/fechar)
  const lastPromptRef = useRef<string | null>(null);

  // A cada abertura (ou novo prompt do hero): continua a MESMA sessão (resume) ou cria uma nova.
  useEffect(() => {
    if (!open) return;
    void onOpen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialPrompt]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing, quote]);

  // Ao PERDER a sessão (logout / 401), zera a conversa local — o próximo usuário não herda a anterior.
  useEffect(() => {
    if (token) return;
    genRef.current++; // invalida continuações em voo
    sessionRef.current = null;
    lastPromptRef.current = null;
    setMessages([]);
    setQuote(null);
    setHandoff(false);
    setConfirmedOutcome(null);
    setFailed(false);
  }, [token]);

  const onOpen = async () => {
    const prompt = initialPrompt.trim();
    if (!sessionRef.current) {
      // Só inicia a conversa quando há um prompt DIGITADO pelo usuário (fluxo signup). Numa reabertura pura
      // ("Abrir a conversa" / login sem prompt, ou após reload que zera a sessão em memória) o chat abre
      // vazio — a 1ª mensagem do usuário (handleSend) cria a sessão. Evita disparar um prompt não solicitado
      // e criar uma sessão órfã (fix do review 3.2).
      if (prompt) await startSession(prompt);
    } else if (prompt && prompt !== lastPromptRef.current) {
      // Reabriu com um novo prompt → continua a conversa (mesma sessão).
      lastPromptRef.current = prompt;
      setMessages((m) => [...m, { id: nextId(), role: "user", text: prompt }]);
      await sendTurnGuarded(prompt, genRef.current);
    }
  };

  const startSession = async (prompt: string) => {
    const gen = ++genRef.current; // nova geração: continuações antigas passam a ser ignoradas
    lastPromptRef.current = prompt;
    setFailed(false);
    setConfirmedOutcome(null); // nova sessão → confirmação zerada
    setMessages([{ id: nextId(), role: "user", text: prompt }]);
    setTyping(true);
    try {
      const { session_id } = await createChatSession(token ?? "");
      if (gen !== genRef.current) return; // superada por outra abertura
      sessionRef.current = session_id;
      await sendTurnGuarded(prompt, gen);
    } catch (err) {
      if (gen !== genRef.current) return;
      setTyping(false);
      if (err instanceof ApiError && err.status === 401) {
        clearSession(); // sessão expirada/inválida → limpa o token e fecha (a UI volta a "não autenticado")
        close();
        return;
      }
      setFailed(true);
    }
  };

  const sendTurnGuarded = async (text: string, gen: number) => {
    const sid = sessionRef.current;
    if (!sid) return;
    setTyping(true);
    try {
      const res = await sendTurn(sid, text, token ?? "");
      if (gen !== genRef.current) return;
      setMessages((m) => [...m, { id: nextId(), role: "assistant", text: res.reply }]);
      if (res.quote) setQuote(res.quote);
      setHandoff(res.handoff_suggested);
    } catch (err) {
      if (gen !== genRef.current) return;
      if (err instanceof ApiError && err.status === 401) {
        clearSession();
        close();
        return;
      }
      setMessages((m) => [
        ...m,
        { id: nextId(), role: "assistant", text: "Tive um problema agora. Pode tentar enviar de novo?" },
      ]);
    } finally {
      if (gen === genRef.current) setTyping(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || typing) return;
    setInput("");
    // Sem sessão (ex.: a criação falhou antes) → (re)cria a conversa a partir desta mensagem.
    if (!sessionRef.current) {
      await startSession(text);
      return;
    }
    track("chat_message", { length: text.length });
    setMessages((m) => [...m, { id: nextId(), role: "user", text }]);
    await sendTurnGuarded(text, genRef.current);
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

              {quote && !typing && (
                <QuoteCard
                  quote={quote}
                  sessionId={sessionRef.current ?? undefined}
                  token={token ?? undefined}
                  outcome={confirmedOutcome}
                  onConfirmed={setConfirmedOutcome}
                />
              )}

              {failed && !typing && (
                <div className="flex flex-col items-start gap-2 pl-10">
                  <p className="text-sm text-muted-foreground">Não consegui iniciar a conversa agora.</p>
                  <Button
                    size="sm"
                    onClick={() => void startSession(lastPromptRef.current ?? DEFAULT_PROMPT)}
                    className="rounded-full bg-accent text-accent-foreground hover:brightness-105"
                  >
                    <RotateCw className="size-4" /> Tentar novamente
                  </Button>
                </div>
              )}

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
