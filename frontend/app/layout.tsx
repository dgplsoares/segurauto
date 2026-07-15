import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "SegurAuto — Seguro de auto rápido e sem burocracia",
  description: "Cote seu seguro de automóvel em minutos.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
