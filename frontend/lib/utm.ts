// Serviço FAKE de UTM (F5c.2): sorteia uma campanha por submissão (2 Meta + 2 Google). A plataforma vira
// o `source` do lead (atribuição). A campanha específica vai para a instrumentação. Real = F6 (Click_ID).
export interface UtmCampaign {
  platform: "meta" | "google";
  campaign: string;
}

const CAMPAIGNS: UtmCampaign[] = [
  { platform: "meta", campaign: "meta_roubo_furto" },
  { platform: "meta", campaign: "meta_cotacao_rapida" },
  { platform: "google", campaign: "google_seguro_auto" },
  { platform: "google", campaign: "google_menor_preco" },
];

export function pickCampaign(): UtmCampaign {
  return CAMPAIGNS[Math.floor(Math.random() * CAMPAIGNS.length)];
}

/** Click ID de campanha na URL da LP (gclid=Google, fbclid=Meta). `undefined` fora do navegador/sem param. */
export function readClickId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const params = new URLSearchParams(window.location.search);
  return params.get("gclid") ?? params.get("fbclid") ?? undefined;
}
