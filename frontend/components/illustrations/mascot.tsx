/**
 * Mascote ORIGINAL da SegurAuto: uma gota/escudo arredondado com rostinho
 * amigável (line-art, currentColor). NÃO é um marshmallow — desenho próprio.
 */
export function IllustrationMascot({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 160"
      fill="none"
      className={className}
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {/* linha do horizonte */}
      <path d="M6 128h60" />
      <path d="M134 128h60" />
      {/* corpo em formato de escudo arredondado espiando */}
      <path d="M66 128c0-24 15-44 34-44s34 20 34 44" />
      <path d="M66 128h68" />
      {/* olhos */}
      <circle cx="88" cy="110" r="4" />
      <circle cx="112" cy="110" r="4" />
      {/* sorriso */}
      <path d="M90 120c4 5 16 5 20 0" />
      {/* mãozinhas segurando a linha */}
      <path d="M66 128c-6 0-10-4-10-9" />
      <path d="M134 128c6 0 10-4 10-9" />
      {/* brilho/antena de escudo */}
      <path d="M100 84V72" />
      <path d="M100 68a4 4 0 100-8 4 4 0 000 8Z" />
    </svg>
  );
}
