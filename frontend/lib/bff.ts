// BFF fino: os route handlers (/api/*) só proxiam para o ai-service, sem lógica de negócio
// (CLAUDE.md — "camada de apresentação fina sobre o BFF"). A URL do serviço vem do ambiente
// (docker-compose injeta AI_SERVICE_URL=http://ai-service:8000; fora do container, localhost).
export const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? "http://localhost:8000";

type ProxyInit = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
};

/** Encaminha uma requisição JSON ao ai-service, repassando status e corpo tal como vieram. */
export async function proxyJson(path: string, init: ProxyInit = {}): Promise<Response> {
  let upstream: Response;
  try {
    upstream = await fetch(`${AI_SERVICE_URL}${path}`, {
      method: init.method ?? "POST",
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      cache: "no-store",
    });
  } catch {
    return Response.json({ error: "upstream_unreachable" }, { status: 502 });
  }
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
