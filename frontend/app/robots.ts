import type { MetadataRoute } from "next";

// /robots.txt — conteúdo FICTÍCIO não deve ser rastreado (decisão: NÃO indexar, mesmo em produção).
// Runtime (force-dynamic) p/ flipar sem rebuild caso um dia mude: ALLOW_INDEXING=true libera; senão bloqueia.
export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  const allow = process.env.ALLOW_INDEXING === "true";
  return { rules: { userAgent: "*", ...(allow ? { allow: "/" } : { disallow: "/" }) } };
}
