/** Ilustração original line-art de um carro estilizado (usa currentColor). */
export function IllustrationCar({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 240 150"
      fill="none"
      className={className}
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M22 104h196" />
      <path d="M40 104c-8 0-14-6-14-14 0-6 4-11 10-13l12-4 18-24c4-5 10-8 16-8h44c7 0 13 3 17 9l14 22 22 6c8 2 13 9 13 17 0 5-4 9-9 9" />
      <path d="M70 41v33" />
      <path d="M112 41v33" />
      <path d="M60 74h96" />
      <circle cx="74" cy="106" r="16" />
      <circle cx="74" cy="106" r="5" />
      <circle cx="174" cy="106" r="16" />
      <circle cx="174" cy="106" r="5" />
      <path d="M196 84h12" />
      <path d="M30 90h10" />
    </svg>
  );
}
