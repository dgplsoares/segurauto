/** Doodles line-art lúdicos (nuvens, árvore, cata-vento) — currentColor. */
export function IllustrationNature({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 320 120"
      fill="none"
      className={className}
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {/* nuvem esquerda */}
      <path d="M20 44c-8 0-14-6-14-13S12 18 20 18c2-7 9-12 17-12s14 5 16 12c7 0 13 6 13 13s-6 13-14 13H20Z" />
      {/* nuvem direita */}
      <path d="M262 34c-6 0-11-5-11-11s5-11 11-11c2-5 7-9 13-9s11 4 13 9c6 0 11 5 11 11s-5 11-12 11h-25Z" />
      {/* arvorezinha */}
      <path d="M92 112V78" />
      <circle cx="92" cy="58" r="20" />
      {/* cata-vento */}
      <path d="M228 112V64" />
      <path d="M228 64l18-8-6 18-12-10Z" />
      <path d="M228 64l-18-8 6 18 12-10Z" />
      <path d="M228 64l8 18 10-12-18-6Z" />
      {/* broto central */}
      <path d="M160 112V88" />
      <path d="M160 92c-8 0-14-6-14-12 8 0 14 6 14 12Z" />
      <path d="M160 96c8 0 14-6 14-12-8 0-14 6-14 12Z" />
    </svg>
  );
}
