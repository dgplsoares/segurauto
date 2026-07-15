# Arquitetura Visual da Landing Page — SegurAuto

> Plano de seções e elementos da LP e seu papel na conversão. **v1 de referência** — a ser
> **reconciliado com o export do Figma Make** quando ele entrar em `frontend/`. O objetivo do
> layout é **uma ação primária: capturar o lead** (cotação), com o mínimo de fricção.

## Princípios de conversão

- **Uma ação primária** por tela: cotar/enviar lead. CTAs secundários reforçam a mesma ação.
- **Formulário curto e progressivo** (poucos campos above the fold; o resto vem depois/no enriquecimento).
- **Confiança antes de pedir dados** (selos, parceiros, prova social próximos ao formulário).
- **CTA persistente** (sticky) e reconversão ao longo da página.
- **Suporte por IA** sempre acessível (widget), que também é um caminho de captura por conversa.
- **Performance e acessibilidade**: hero leve (bom LCP), responsivo mobile-first, contraste/labels.
- **LGPD**: consentimento explícito no formulário; PII tratada com cuidado.

## Seções (topo → base)

| # | Seção | Elementos | Papel na conversão |
|---|---|---|---|
| 1 | **Header / Nav** | Logo, âncoras (Como funciona · Coberturas · FAQ), **CTA "Cotar agora"** | Orientação + CTA sempre visível (sticky) |
| 2 | **Hero** | Headline de valor, subheadline, **formulário de cotação** (lead form principal), selos de confiança, imagem/ilustração | **Captura primária** above the fold |
| 3 | **Prova social / confiança** | Logos de seguradoras parceiras, nº de clientes, avaliações, selos de segurança | Reduz fricção e objeção de confiança |
| 4 | **Como funciona** | 3 passos: **Cote → Compare → Contrate** (ícones + microcopy) | Clareza do processo, reduz incerteza |
| 5 | **Coberturas / Benefícios** | Cards: roubo/furto, colisão, terceiros, **assistência 24h**, carro reserva | Comunica valor; ancora a decisão |
| 6 | **Diferenciais** | "Por que SegurAuto": rapidez, **atendimento por IA**, comparação de preços | Diferenciação competitiva |
| 7 | **Depoimentos** | Testimonials (foto, nome, nota) | Prova social qualitativa |
| 8 | **Oferta / Reconversão** | Bloco de CTA com **formulário curto** ou botão "Simular agora" | Segunda chance de conversão |
| 9 | **FAQ** | Perguntas comuns (também **alimenta o RAG** do suporte) | Remove objeções + SEO |
| 10 | **Widget de suporte (flutuante)** | Chat de IA no canto inferior direito | Suporte + captura por conversa |
| 11 | **Footer** | Links, contato, **privacidade/LGPD**, redes sociais | Confiança/legal |

## Formulário de captura — contrato de dados (form → lead)

Campos mínimos (progressivo; começar enxuto para maximizar conversão):

| Campo (form) | Campo (Lead) | Obrigatório | Observação |
|---|---|---|---|
| Nome | `name` | sim | — |
| E-mail | `email` | sim | validação + dedup de negócio |
| Telefone/WhatsApp | `phone` | sim | máscara BR; dedup de negócio |
| Placa **ou** Marca/Modelo/Ano | `vehicle` | sim | placa acelera; modelo é fallback |
| CEP | `zipcode` | sim | região influencia preço |
| Consentimento LGPD | `consent` | sim | checkbox explícito |
| (oculto) `Idempotency-Key` | header | sim | **uuid gerado no client ao carregar o form** |
| (oculto) origem/UTM | `source` | não | atribuição de campanha |

Envio: `LeadForm → POST /api/lead (BFF) → POST /leads (ai-service)`. Resposta rápida (201); o
enriquecimento (qualificação + CRM + Ads) roda no worker.

## Instrumentação de conversão (eventos)

- `lp_view`, `form_view`, `form_start`, `form_submit` (frontend/analytics).
- No submit bem-sucedido: o ai-service registra `lead_received` e o worker dispara os **eventos de
  conversão** para as plataformas de anúncios (`AdsPort`, com `event_id` estável para dedup).
- Widget de suporte: `support_open`, `support_message`.

## Widget de suporte (chat de IA)

- Flutuante, não-bloqueante; abre um painel de chat.
- `SupportChat → POST /api/support (BFF) → POST /support/chat (support_agent, RAG single-turn na V1)`.
- Base de conhecimento inicial = FAQ + materiais SegurAuto (seed do RAG).
- Guardrail contra prompt-injection (input do usuário é dado não-confiável) — a aprofundar.

## Responsividade e estados

- **Mobile-first**; hero e formulário reflow em coluna única.
- Estados do formulário: idle, validando, enviando, sucesso (mensagem + próximo passo), erro (retry
  seguro pela `Idempotency-Key`).
- Acessibilidade: labels associados, foco visível, contraste AA, navegação por teclado.

## Reconciliação com o Figma Make

O layout já desenhado (Next.js) entra em `frontend/`. Ao integrar:
- Mapear as seções reais do export para esta tabela (ajustar nomes/ordem conforme o design).
- Tratar a LP como **camada de apresentação fina sobre o BFF** — nenhuma lógica de negócio no front.
- Extrair os textos para um **content provider** (estático na V1), preparando o CMS da V2.
