"use client";

import type { ReactNode } from "react";
import { Bot } from "lucide-react";
import { motion } from "motion/react";
import { cn } from "./ui/utils";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

// Renderiza o markdown inline comum do LLM (**negrito**, *itálico*, `código`) + quebras de linha e bullets,
// como elementos React — XSS-safe (nada de innerHTML; o React escapa o texto). Cobre o caso reportado (o
// negrito não renderizava) sem adicionar dependência. Só é aplicado às mensagens do assistente.
function renderInline(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`)/g; // negrito primeiro (match mais longo), depois itálico/código
  let last = 0;
  let k = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) nodes.push(<strong key={`${keyBase}-${k++}`}>{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`"))
      nodes.push(
        <code key={`${keyBase}-${k++}`} className="rounded bg-black/10 px-1 py-0.5 text-[0.85em]">
          {t.slice(1, -1)}
        </code>,
      );
    else nodes.push(<em key={`${keyBase}-${k++}`}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function renderRich(text: string): ReactNode {
  return text.split("\n").map((line, i) => {
    if (line.trim() === "") return <span key={i} className="block h-2" />; // linha em branco = respiro
    const isBullet = /^\s*[-*]\s+/.test(line);
    const content = isBullet ? line.replace(/^\s*[-*]\s+/, "") : line;
    return (
      <span key={i} className={cn("block", isBullet && "-indent-3 pl-3")}>
        {isBullet && "• "}
        {renderInline(content, `l${i}`)}
      </span>
    );
  });
}

export function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn("flex gap-2.5", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Bot className="size-4" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md bg-secondary text-secondary-foreground",
        )}
      >
        {/* mensagem do usuário = texto puro (não interpreta markdown do input); assistente = markdown inline */}
        {isUser ? message.text : renderRich(message.text)}
      </div>
    </motion.div>
  );
}

export function TypingBubble() {
  return (
    <div className="flex gap-2.5">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Bot className="size-4" />
      </div>
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-md bg-secondary px-4 py-3.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  );
}
