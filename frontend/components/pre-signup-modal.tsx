"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { Loader2, ShieldCheck } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Checkbox } from "./ui/checkbox";
import { cn } from "./ui/utils";
import { useLeadFlow } from "../lib/lead-flow-context";
import { ApiError } from "../lib/api";

interface FormValues {
  name: string;
  email: string;
  phone: string;
  vehicle: string;
  consent: boolean;
}

/** Máscara de telefone BR: (11) 91234-5678 */
function maskPhone(value: string) {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 2) return digits.replace(/(\d{0,2})/, "($1");
  if (digits.length <= 6) return digits.replace(/(\d{2})(\d{0,4})/, "($1) $2");
  if (digits.length <= 10)
    return digits.replace(/(\d{2})(\d{4})(\d{0,4})/, "($1) $2-$3");
  return digits.replace(/(\d{2})(\d{5})(\d{0,4})/, "($1) $2-$3");
}

export function PreSignupModal() {
  const { step, initialPrompt, submitLead, close } = useLeadFlow();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    setError,
    clearErrors,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    defaultValues: { name: "", email: "", phone: "", vehicle: "", consent: false },
  });

  const consent = watch("consent");
  const phone = watch("phone");

  const onSubmit = handleSubmit(async (data) => {
    if (!data.consent) {
      setError("consent", { message: "É preciso aceitar para continuar." });
      return;
    }
    setServerError(null);
    try {
      await submitLead({
        name: data.name,
        email: data.email,
        phone: data.phone,
        vehicle: data.vehicle,
        consent: data.consent,
      });
      reset();
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "Algo deu errado. Tente novamente em instantes.";
      setServerError(message);
    }
  });

  const fieldError = (name: keyof FormValues) => errors[name]?.message;

  return (
    <Dialog
      open={step === "presignup"}
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <DialogContent className="rounded-3xl sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl">Quase lá! Vamos te conhecer.</DialogTitle>
          <DialogDescription>
            É rapidinho. Depois disso, o consultor já começa a te ajudar.
          </DialogDescription>
        </DialogHeader>

        {initialPrompt && (
          <div className="rounded-2xl bg-secondary px-4 py-3 text-sm text-secondary-foreground">
            <span className="text-muted-foreground">Sua pergunta: </span>
            <span className="italic">“{initialPrompt}”</span>
          </div>
        )}

        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="name">Nome completo</Label>
            <Input
              id="name"
              placeholder="Ex.: Maria Silva"
              aria-invalid={!!errors.name}
              {...register("name", {
                required: "Informe seu nome completo.",
                minLength: { value: 3, message: "Nome muito curto." },
              })}
            />
            {fieldError("name") && (
              <p className="text-sm text-destructive">{fieldError("name")}</p>
            )}
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="email">E-mail</Label>
            <Input
              id="email"
              type="email"
              placeholder="voce@email.com"
              aria-invalid={!!errors.email}
              {...register("email", {
                required: "Informe seu e-mail.",
                pattern: {
                  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                  message: "E-mail inválido.",
                },
              })}
            />
            {fieldError("email") && (
              <p className="text-sm text-destructive">{fieldError("email")}</p>
            )}
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="phone">Telefone / WhatsApp</Label>
            <Input
              id="phone"
              inputMode="tel"
              placeholder="(11) 91234-5678"
              aria-invalid={!!errors.phone}
              {...register("phone", {
                required: "Informe seu telefone.",
                validate: (v) =>
                  v.replace(/\D/g, "").length >= 10 || "Telefone incompleto.",
              })}
              value={phone}
              onChange={(e) =>
                setValue("phone", maskPhone(e.target.value), { shouldValidate: false })
              }
            />
            {fieldError("phone") && (
              <p className="text-sm text-destructive">{fieldError("phone")}</p>
            )}
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="vehicle">Placa do veículo</Label>
            <Input
              id="vehicle"
              placeholder="ABC1D23 (ou marca/modelo/ano)"
              aria-invalid={!!errors.vehicle}
              className="uppercase placeholder:normal-case"
              {...register("vehicle", {
                required: "Informe a placa ou o modelo do veículo.",
              })}
            />
            {fieldError("vehicle") && (
              <p className="text-sm text-destructive">{fieldError("vehicle")}</p>
            )}
          </div>

          <div className="flex items-start gap-2.5">
            <Checkbox
              id="consent"
              checked={consent}
              onCheckedChange={(v) => {
                setValue("consent", v === true);
                if (v === true) clearErrors("consent");
              }}
              aria-invalid={!!errors.consent}
              className={cn("mt-0.5", errors.consent && "border-destructive")}
            />
            <label htmlFor="consent" className="text-sm leading-snug text-muted-foreground">
              Autorizo o tratamento dos meus dados conforme a{" "}
              <span className="text-primary underline">Política de Privacidade (LGPD)</span>{" "}
              para receber a cotação.
            </label>
          </div>
          {errors.consent && (
            <p className="-mt-2 text-sm text-destructive">{errors.consent.message}</p>
          )}

          {serverError && (
            <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {serverError}
            </p>
          )}

          <Button
            type="submit"
            size="lg"
            disabled={isSubmitting}
            className="mt-1 rounded-2xl bg-accent text-accent-foreground hover:brightness-105"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="animate-spin" /> Enviando…
              </>
            ) : (
              "Continuar"
            )}
          </Button>

          <p className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5 text-accent" />
            Seus dados estão protegidos e nunca serão compartilhados sem permissão.
          </p>
        </form>
      </DialogContent>
    </Dialog>
  );
}
