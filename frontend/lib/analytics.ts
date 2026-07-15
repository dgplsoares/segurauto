/**
 * Stub de instrumentação de conversão. Faz apenas console.log por enquanto.
 * Na integração, plugar aqui o provedor real (GA/Meta/etc.).
 */

export type AnalyticsEvent =
  | "lp_view"
  | "prompt_focus"
  | "prompt_submit"
  | "signup_view"
  | "signup_submit"
  | "otp_view"
  | "otp_verified"
  | "chat_message"
  | "quote_confirm";

export function track(event: AnalyticsEvent, payload?: Record<string, unknown>) {
  // TODO(integração): enviar para o provedor de analytics real.
  // eslint-disable-next-line no-console
  console.log(`[analytics] ${event}`, payload ?? {});
}
