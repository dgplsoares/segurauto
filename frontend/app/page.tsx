"use client";

// LP funcional MÍNIMA (Fase 4c) — smoke test visual do fluxo prompt-first, reconciliável depois com
// o export do Figma Make (ver .claude/plan/arquitetura-visual-lp.md). Só elementos funcionais:
// hero com campo de prompt → modal de pré-cadastro → modal de OTP (5 dígitos + timer 30s) → chat.
// Nenhuma lógica de negócio aqui: as chamadas vão ao BFF (/api/*), que proxia o ai-service.
import { useEffect, useRef, useState } from "react";
import type { CSSProperties, FormEvent, KeyboardEvent } from "react";

type Stage = "hero" | "signup" | "login" | "otp" | "chat";
type Msg = { role: "user" | "assistant"; text: string };

const PLACEHOLDERS = [
  "Quero cotar o seguro do meu HB20…",
  "Meu seguro cobre roubo e furto?",
  "Quanto custa para um Onix 2020?",
];

const s = {
  input: {
    width: "100%", padding: "12px 14px", borderRadius: 10, border: "1px solid var(--line)",
    marginTop: 6, background: "#fff",
  } as CSSProperties,
  label: { display: "block", marginTop: 14, fontSize: 14, fontWeight: 600 } as CSSProperties,
  primaryBtn: {
    width: "100%", marginTop: 22, padding: "13px 16px", borderRadius: 12, border: "none",
    background: "var(--primary)", color: "#fff", fontWeight: 700, fontSize: 16,
  } as CSSProperties,
  overlay: {
    position: "fixed", inset: 0, background: "rgba(15,23,42,0.55)", display: "flex",
    alignItems: "center", justifyContent: "center", padding: 16, zIndex: 50,
  } as CSSProperties,
  card: {
    background: "#fff", borderRadius: 16, padding: 28, width: "100%", maxWidth: 420,
    boxShadow: "0 20px 50px rgba(15,23,42,0.25)",
  } as CSSProperties,
  error: { color: "var(--danger)", fontSize: 14, marginTop: 12 } as CSSProperties,
};

/** 5 caixas de um dígito com avanço/retorno automático de foco. */
function OtpBoxes({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);
  const digits = Array.from({ length: 5 }, (_, i) => value[i] ?? "");

  function setAt(i: number, raw: string) {
    const d = raw.replace(/\D/g, "").slice(-1);
    const next = digits.slice();
    next[i] = d;
    onChange(next.join(""));
    if (d && i < 4) refs.current[i + 1]?.focus();
  }
  function onKeyDown(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !digits[i] && i > 0) refs.current[i - 1]?.focus();
  }
  return (
    <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 18 }}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => { refs.current[i] = el; }}
          value={d}
          inputMode="numeric"
          maxLength={1}
          aria-label={`Dígito ${i + 1}`}
          onChange={(e) => setAt(i, e.target.value)}
          onKeyDown={(e) => onKeyDown(i, e)}
          style={{ width: 46, height: 54, textAlign: "center", fontSize: 22, borderRadius: 10, border: "1px solid var(--line)" }}
        />
      ))}
    </div>
  );
}

export default function Home() {
  const [stage, setStage] = useState<Stage>("hero");
  const [prompt, setPrompt] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [consent, setConsent] = useState(false);
  const [idemKey, setIdemKey] = useState("");
  const [code, setCode] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // OTP: timer de reenvio (30s), reiniciado a cada envio.
  const [secondsLeft, setSecondsLeft] = useState(30);
  const [resendNonce, setResendNonce] = useState(0);

  // Chat.
  const [messages, setMessages] = useState<Msg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [typing, setTyping] = useState(false);

  // Placeholder animado do hero.
  const [phIdx, setPhIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setPhIdx((i) => (i + 1) % PLACEHOLDERS.length), 2800);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (stage !== "otp") return;
    setSecondsLeft(30);
    const t = setInterval(() => setSecondsLeft((v) => (v > 0 ? v - 1 : 0)), 1000);
    return () => clearInterval(t);
  }, [stage, resendNonce]);

  function reset() {
    setError(null);
    setCode("");
  }
  function openSignup() {
    reset();
    setIdemKey(typeof crypto !== "undefined" ? crypto.randomUUID() : String(Date.now()));
    setStage("signup");
  }
  function openLogin() {
    reset();
    setStage("login");
  }
  function close() {
    reset();
    setStage("hero");
  }

  async function requestOtp(mail: string) {
    // 202 neutro sempre — não revela se o e-mail existe.
    await fetch("/api/auth/request-otp", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: mail }),
    });
  }

  async function submitSignup(e: FormEvent) {
    e.preventDefault();
    if (!consent) { setError("É necessário aceitar o consentimento (LGPD)."); return; }
    setBusy(true); setError(null);
    try {
      const res = await fetch("/api/lead", {
        method: "POST",
        headers: { "content-type": "application/json", "Idempotency-Key": idemKey },
        // CEP é coletado no chat (F5); enquanto o backend exige, enviamos um provisório.
        body: JSON.stringify({ name, email, phone, vehicle, zipcode: "00000000", consent, source: "landing_page" }),
      });
      if (res.status !== 201 && res.status !== 200) {
        setError("Não foi possível concluir o cadastro. Tente novamente.");
        return;
      }
      await requestOtp(email);
      setStage("otp");
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  async function submitLogin(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await requestOtp(email);
      setStage("otp");
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  async function submitOtp(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const res = await fetch("/api/auth/verify-otp", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, code }),
      });
      if (res.status !== 200) {
        setError("Código inválido ou expirado.");
        return;
      }
      const data = (await res.json()) as { token: string };
      setToken(data.token);
      setStage("chat");
      const first = prompt.trim();
      if (first) void sendChat(first, data.token);
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    if (secondsLeft > 0) return;
    await requestOtp(email);
    setResendNonce((n) => n + 1);
  }

  async function sendChat(text: string, tok: string | null = token) {
    const msg = text.trim();
    if (!msg || !tok) return;
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setChatInput("");
    setTyping(true);
    try {
      const res = await fetch("/api/support", {
        method: "POST",
        headers: { "content-type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ message: msg }),
      });
      if (!res.ok) {
        setMessages((m) => [...m, { role: "assistant", text: "Desculpe, tive um problema agora. Pode tentar de novo?" }]);
        return;
      }
      const data = (await res.json()) as { answer: string; handoff_suggested: boolean };
      const suffix = data.handoff_suggested ? "\n\n💬 Posso te encaminhar a um corretor, se preferir." : "";
      setMessages((m) => [...m, { role: "assistant", text: data.answer + suffix }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Falha de conexão com o consultor. Tente novamente." }]);
    } finally {
      setTyping(false);
    }
  }

  if (stage === "chat") return <Chat messages={messages} typing={typing} value={chatInput} onChange={setChatInput} onSend={() => void sendChat(chatInput)} />;

  return (
    <main>
      {/* Header */}
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 24px", maxWidth: 1100, margin: "0 auto" }}>
        <strong style={{ fontSize: 20, color: "var(--primary)" }}>SegurAuto</strong>
        <button onClick={openLogin} style={{ background: "none", border: "none", color: "var(--primary)", fontWeight: 600 }}>
          Já tem cadastro? Entre
        </button>
      </header>

      {/* Hero prompt-first */}
      <section style={{ maxWidth: 720, margin: "0 auto", padding: "56px 24px 40px", textAlign: "center" }}>
        <h1 style={{ fontSize: 42, lineHeight: 1.1, margin: 0 }}>Seguro de auto, sem burocracia.</h1>
        <p style={{ fontSize: 19, color: "var(--muted)", marginTop: 14 }}>
          Converse agora com o nosso consultor de IA e receba sua cotação em minutos.
        </p>

        <form
          onSubmit={(e) => { e.preventDefault(); openSignup(); }}
          style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 30, padding: "8px 8px 8px 18px",
            border: "2px solid var(--accent)", borderRadius: 999, background: "#fff", boxShadow: "0 8px 24px rgba(6,182,212,0.15)" }}
        >
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={PLACEHOLDERS[phIdx]}
            aria-label="Converse com o consultor de IA"
            style={{ flex: 1, border: "none", outline: "none", fontSize: 17, background: "transparent", padding: "8px 4px" }}
          />
          <button type="submit" aria-label="Começar a conversa"
            style={{ width: 46, height: 46, minWidth: 46, borderRadius: 999, border: "none", background: "var(--accent)", color: "#fff", fontSize: 22 }}>
            →
          </button>
        </form>
        <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 14 }}>
          🔒 Seus dados são protegidos (LGPD) · ⚡ Resposta na hora · ⭐ 4,8/5 de satisfação
        </p>
      </section>

      {stage === "signup" && (
        <Modal onClose={close} title="Quase lá! Vamos te conhecer.">
          {prompt.trim() && <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>Sua pergunta: “{prompt.trim()}”</p>}
          <form onSubmit={submitSignup}>
            <label style={s.label}>Nome completo
              <input style={s.input} value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label style={s.label}>E-mail
              <input style={s.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label style={s.label}>Telefone / WhatsApp
              <input style={s.input} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="(11) 90000-0000" required />
            </label>
            <label style={s.label}>Placa do veículo
              <input style={s.input} value={vehicle} onChange={(e) => setVehicle(e.target.value)} placeholder="ABC1D23" required />
            </label>
            <label style={{ display: "flex", gap: 8, marginTop: 16, fontSize: 14, alignItems: "flex-start" }}>
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} style={{ marginTop: 3 }} />
              <span>Autorizo o contato e o tratamento dos meus dados conforme a Política de Privacidade (LGPD).</span>
            </label>
            {error && <p style={s.error}>{error}</p>}
            <button type="submit" style={s.primaryBtn} disabled={busy}>{busy ? "Enviando…" : "Continuar"}</button>
          </form>
        </Modal>
      )}

      {stage === "login" && (
        <Modal onClose={close} title="Entrar">
          <p style={{ fontSize: 14, color: "var(--muted)", marginTop: 4 }}>Informe seu e-mail para receber um código de acesso.</p>
          <form onSubmit={submitLogin}>
            <label style={s.label}>E-mail
              <input style={s.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            {error && <p style={s.error}>{error}</p>}
            <button type="submit" style={s.primaryBtn} disabled={busy}>{busy ? "Enviando…" : "Enviar código"}</button>
          </form>
        </Modal>
      )}

      {stage === "otp" && (
        <Modal onClose={close} title="Verifique seu e-mail">
          <p style={{ fontSize: 14, color: "var(--muted)", marginTop: 4 }}>
            Enviamos um código de 5 dígitos para <strong>{email}</strong>.
          </p>
          <form onSubmit={submitOtp}>
            <OtpBoxes value={code} onChange={setCode} />
            {error && <p style={{ ...s.error, textAlign: "center" }}>{error}</p>}
            <button type="submit" style={s.primaryBtn} disabled={busy || code.length < 5}>{busy ? "Verificando…" : "Verificar"}</button>
          </form>
          <p style={{ textAlign: "center", fontSize: 14, color: "var(--muted)", marginTop: 16 }}>
            {secondsLeft > 0
              ? <>Reenviar código em {secondsLeft}s</>
              : <button onClick={resend} style={{ background: "none", border: "none", color: "var(--primary)", fontWeight: 600 }}>Reenviar código</button>}
          </p>
        </Modal>
      )}
    </main>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div style={s.overlay} onClick={onClose} role="dialog" aria-modal="true" aria-label={title}>
      <div style={s.card} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: 22, margin: 0 }}>{title}</h2>
          <button onClick={onClose} aria-label="Fechar" style={{ background: "none", border: "none", fontSize: 22, color: "var(--muted)" }}>×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Chat({ messages, typing, value, onChange, onSend }: {
  messages: Msg[]; typing: boolean; value: string; onChange: (v: string) => void; onSend: () => void;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, typing]);
  return (
    <main style={{ display: "flex", flexDirection: "column", height: "100vh", maxWidth: 760, margin: "0 auto" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 20px", borderBottom: "1px solid var(--line)" }}>
        <span style={{ width: 36, height: 36, borderRadius: 999, background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>SA</span>
        <div>
          <strong>Consultor SegurAuto</strong>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>online agora</div>
        </div>
      </header>

      <div style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ alignSelf: m.role === "user" ? "flex-end" : "flex-start", maxWidth: "78%",
            background: m.role === "user" ? "var(--primary)" : "#fff", color: m.role === "user" ? "#fff" : "var(--ink)",
            border: m.role === "user" ? "none" : "1px solid var(--line)", padding: "10px 14px", borderRadius: 14, whiteSpace: "pre-wrap" }}>
            {m.text}
          </div>
        ))}
        {typing && (
          <div className="typing" style={{ alignSelf: "flex-start", background: "#fff", border: "1px solid var(--line)", padding: "10px 14px", borderRadius: 14 }}>
            <span>●</span><span>●</span><span>●</span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); onSend(); }}
        style={{ display: "flex", gap: 8, padding: 16, borderTop: "1px solid var(--line)" }}>
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="Escreva sua mensagem…"
          aria-label="Mensagem" style={{ flex: 1, padding: "12px 14px", borderRadius: 10, border: "1px solid var(--line)" }} />
        <button type="submit" style={{ padding: "12px 20px", borderRadius: 10, border: "none", background: "var(--primary)", color: "#fff", fontWeight: 700 }}>
          Enviar
        </button>
      </form>
    </main>
  );
}
