/** Ilustração original line-art: pessoa tranquila (usa currentColor). */
export function IllustrationDriver({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 170"
      fill="none"
      className={className}
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {/* chão */}
      <path d="M12 150h176" />
      {/* nuvem/arbusto atrás */}
      <path d="M40 96c-11 0-20-9-20-20 0-9 6-16 14-19 2-12 12-21 24-21 10 0 19 6 22 15 10 1 18 9 18 20 0 12-9 21-21 21H40Z" />
      {/* zzz (descanso) */}
      <path d="M120 40h16l-16 16h16" />
      <path d="M142 22h11l-11 11h11" />
      {/* figura sentada relaxada */}
      <circle cx="150" cy="96" r="14" />
      <path d="M150 110c-16 0-28 12-28 28v12h56v-12c0-16-12-28-28-28Z" />
      <path d="M150 96c3-2 6-2 9 0" />
    </svg>
  );
}
