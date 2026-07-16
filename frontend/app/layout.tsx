import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

// Conteúdo FICTÍCIO (seguradora/dados fake) → NÃO indexar, por decisão, MESMO em produção. O flag
// ALLOW_INDEXING existe (=true liberaria), mas fica OFF permanente. Default (sem o flag) = noindex, nofollow.
const allowIndexing = process.env.ALLOW_INDEXING === "true";

export const metadata: Metadata = {
  title: "SegurAuto — Seguro de auto rápido e sem burocracia",
  description: "Cote seu seguro de automóvel em minutos.",
  robots: allowIndexing ? undefined : { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
