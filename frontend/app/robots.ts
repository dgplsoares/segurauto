import type { MetadataRoute } from "next";

// /robots.txt — homolog remoto NÃO deve ser rastreado por buscadores. Avaliado em runtime (força dynamic)
// para flipar sem rebuild: ALLOW_INDEXING=true (prod real) libera; qualquer outro valor bloqueia tudo.
export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  const allow = process.env.ALLOW_INDEXING === "true";
  return { rules: { userAgent: "*", ...(allow ? { allow: "/" } : { disallow: "/" }) } };
}
