/**
 * Divisor em onda entre seções. A cor vem de `currentColor` — defina a cor do
 * texto no wrapper (ex.: text-surface-navy) e a onda assume essa cor.
 * `flip` inverte verticalmente (onda apontando para cima).
 */
export function WaveDivider({
  className,
  flip = false,
}: {
  className?: string;
  flip?: boolean;
}) {
  return (
    <div className={className} aria-hidden="true">
      <svg
        viewBox="0 0 1440 80"
        preserveAspectRatio="none"
        className={`block h-[60px] w-full sm:h-[80px] ${flip ? "rotate-180" : ""}`}
      >
        <path
          fill="currentColor"
          d="M0 40c180-40 360-40 540-16 200 26 400 52 620 20 120-18 200-30 280-24v84H0V40Z"
        />
      </svg>
    </div>
  );
}
