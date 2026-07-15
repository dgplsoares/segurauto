import type { ReactNode } from "react";

/** Moldura de celular que renderiza `children` como a tela do app. */
export function PhoneMockup({ children }: { children: ReactNode }) {
  return (
    <div className="relative mx-auto w-full max-w-[300px]">
      {/* blob de fundo suave */}
      <div className="pointer-events-none absolute -right-6 top-10 -z-10 size-56 rounded-full bg-secondary blur-2xl" />
      <div className="rounded-[2.5rem] border-[10px] border-[#1a2330] bg-[#1a2330] shadow-2xl">
        <div className="relative overflow-hidden rounded-[1.8rem] bg-white">
          {/* notch */}
          <div className="absolute left-1/2 top-0 z-10 h-5 w-28 -translate-x-1/2 rounded-b-2xl bg-[#1a2330]" />
          <div className="min-h-[520px] px-4 pb-6 pt-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
