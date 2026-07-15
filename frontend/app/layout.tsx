import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

// Homolog remoto = NÃO indexar (é um ambiente de teste que funciona como prod). Na prod real, ligue com
// ALLOW_INDEXING=true para permitir a indexação. Default (sem o flag) = noindex, nofollow.
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
