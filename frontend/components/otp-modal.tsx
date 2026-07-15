"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, MailCheck } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "./ui/input-otp";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { cn } from "./ui/utils";
import { useLeadFlow } from "../lib/lead-flow-context";
import { ApiError } from "../lib/api";

const RESEND_SECONDS = 30;

export function OtpModal() {
  const { step, mode, email, verify, resendOtp, submitLoginEmail, close } = useLeadFlow();

  // Sub-etapa do login: pedir o e-mail antes do código.
  const [loginEmail, setLoginEmail] = useState("");
  const [askingEmail, setAskingEmail] = useState(mode === "login" && !email);

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [seconds, setSeconds] = useState(RESEND_SECONDS);
  const [sendingEmail, setSendingEmail] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const open = step === "otp";

  // Reset ao abrir.
  useEffect(() => {
    if (open) {
      setCode("");
      setError(null);
      setSeconds(RESEND_SECONDS);
      setAskingEmail(mode === "login" && !email);
      setLoginEmail("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Timer regressivo (só quando o código já está sendo pedido).
  useEffect(() => {
    if (!open || askingEmail) return;
    timerRef.current = setInterval(() => {
      setSeconds((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [open, askingEmail]);

  const targetEmail = email || loginEmail;

  const handleVerify = async (value?: string) => {
    const finalCode = value ?? code;
    if (finalCode.length !== 5) return;
    setVerifying(true);
    setError(null);
    try {
      await verify(finalCode);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Código inválido.";
      setError(message);
      setCode("");
    } finally {
      setVerifying(false);
    }
  };

  const handleResend = async () => {
    await resendOtp();
    setSeconds(RESEND_SECONDS);
    setError(null);
  };

  const handleLoginEmail = async () => {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(loginEmail)) {
      setError("Informe um e-mail válido.");
      return;
    }
    setSendingEmail(true);
    setError(null);
    try {
      await submitLoginEmail(loginEmail);
      setAskingEmail(false);
      setSeconds(RESEND_SECONDS);
    } finally {
      setSendingEmail(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent className="rounded-3xl sm:max-w-md">
        {askingEmail ? (
          <>
            <DialogHeader>
              <DialogTitle className="text-xl">Que bom te ver de novo!</DialogTitle>
              <DialogDescription>
                Informe o e-mail cadastrado para enviarmos um código de acesso.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-1.5">
              <Label htmlFor="login-email">E-mail</Label>
              <Input
                id="login-email"
                type="email"
                autoFocus
                placeholder="voce@email.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLoginEmail()}
                aria-invalid={!!error}
              />
              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>
            <Button
              size="lg"
              disabled={sendingEmail}
              onClick={handleLoginEmail}
              className="rounded-2xl bg-accent text-accent-foreground hover:brightness-105"
            >
              {sendingEmail ? (
                <>
                  <Loader2 className="animate-spin" /> Enviando…
                </>
              ) : (
                "Enviar código"
              )}
            </Button>
          </>
        ) : (
          <>
            <DialogHeader className="items-center text-center sm:text-center">
              <div className="mb-2 flex size-12 items-center justify-center rounded-2xl bg-accent/15 text-accent">
                <MailCheck className="size-6" />
              </div>
              <DialogTitle className="text-xl">Verifique seu e-mail</DialogTitle>
              <DialogDescription>
                Enviamos um código de 5 dígitos para{" "}
                <span className="font-medium text-foreground">{targetEmail}</span>.
                <br />
                <span className="text-xs">(Dica de demonstração: use 12345)</span>
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col items-center gap-4 py-2">
              <InputOTP
                maxLength={5}
                value={code}
                autoFocus
                onChange={(v) => {
                  setCode(v);
                  setError(null);
                  if (v.length === 5) handleVerify(v);
                }}
              >
                <InputOTPGroup className="gap-2">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <InputOTPSlot
                      key={i}
                      index={i}
                      aria-invalid={!!error}
                      className={cn(
                        "size-12 rounded-xl border text-lg",
                        error && "border-destructive text-destructive",
                      )}
                    />
                  ))}
                </InputOTPGroup>
              </InputOTP>

              {error && <p className="text-sm text-destructive">{error}</p>}

              <div className="text-sm text-muted-foreground">
                {seconds > 0 ? (
                  <span>
                    Reenviar código em{" "}
                    <span className="tabular-nums font-medium text-foreground">
                      0:{seconds.toString().padStart(2, "0")}
                    </span>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={handleResend}
                    className="font-medium text-accent underline underline-offset-4 hover:brightness-90"
                  >
                    Reenviar código
                  </button>
                )}
              </div>
            </div>

            <Button
              size="lg"
              disabled={verifying || code.length !== 5}
              onClick={() => handleVerify()}
              className="rounded-2xl bg-accent text-accent-foreground hover:brightness-105"
            >
              {verifying ? (
                <>
                  <Loader2 className="animate-spin" /> Verificando…
                </>
              ) : (
                "Verificar"
              )}
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
