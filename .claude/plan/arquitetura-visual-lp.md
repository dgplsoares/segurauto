# Arquitetura Visual da Landing Page — SegurAuto

> Plano de seções e elementos da LP e seu papel na conversão — a ser **reconciliado com o export do
> Figma Make** quando ele entrar em `frontend/`. A ação primária é **iniciar a conversa com o consultor
> de IA de seguros de auto** por um **campo de prompt no hero** (abordagem **prompt-first**) — é ele que
> capta e conduz à cotação, com o mínimo de fricção.

## Princípios de conversão

- **Uma ação primária** por tela: **começar a conversar** pelo **campo de prompt do hero**. CTAs
  secundários apenas reforçam/rolam até ele.
- **Fricção mínima na entrada**: nada de formulário grande above the fold — só o **campo de prompt**; os
  dados (pré-cadastro) vêm num **modal curto** depois do primeiro toque.
- **Convite claro e animado** ao lado do prompt (placeholder que alterna exemplos), transmitindo que há um
  **consultor de IA** pronto para ajudar.
- **Confiança perto do prompt** (selos, parceiros, prova social) e reconversão ao longo da página.
- **Suporte/consultor por IA** é o coração da LP (não um widget secundário).
- **Performance e acessibilidade**: hero leve (bom LCP), responsivo mobile-first, contraste/labels, o
  campo de prompt com foco visível e navegável por teclado.
- **LGPD**: consentimento explícito no modal de pré-cadastro; PII tratada com cuidado.

## Seções (topo → base)

| # | Seção | Elementos | Papel na conversão |
|---|---|---|---|
| 1 | **Header / Nav** | Logo, âncoras (Como funciona · Coberturas · FAQ), **botão "Falar com o consultor"** (rola até o prompt) | Orientação + reforço da ação primária |
| 2 | **Hero (prompt-first)** | Headline de valor, subheadline, **campo de prompt central** (abaixo do título/subtítulo) com **microcopy convidativa e placeholder animado** ("Quero cotar meu Hb20…", "Meu seguro cobre roubo?…"), botão secundário **"Já tem cadastro? Entre"**, selos de confiança | **Entrada primária** — inicia a conversa com o consultor de IA |
| 3 | **Prova social / confiança** | Logos de seguradoras parceiras, nº de clientes, avaliações, selos de segurança | Reduz fricção e objeção de confiança |
| 4 | **Como funciona** | 3 passos: **Cote → Compare → Contrate** (ícones + microcopy) | Clareza do processo, reduz incerteza |
| 5 | **Coberturas / Benefícios** | Cards: roubo/furto, colisão, terceiros, **assistência 24h**, carro reserva | Comunica valor; ancora a decisão |
| 6 | **Diferenciais** | "Por que SegurAuto": rapidez, **atendimento por IA**, comparação de preços | Diferenciação competitiva |
| 7 | **Depoimentos** | Testimonials (foto, nome, nota) | Prova social qualitativa |
| 8 | **Oferta / Reconversão** | Bloco que **repete o campo de prompt** (ou botão que rola até o hero) | Segunda chance de iniciar a conversa |
| 9 | **FAQ** | Perguntas comuns (também **alimenta o RAG** do suporte) | Remove objeções + SEO |
| 10 | **Widget de suporte (flutuante)** | Chat de IA no canto inferior direito | Suporte + captura por conversa |
| 11 | **Footer** | Links, contato, **privacidade/LGPD**, redes sociais | Confiança/legal |

## Fluxo prompt-first (a espinha da conversão)

A entrada **não é um botão de CTA**, e sim o **campo de prompt no centro do hero** (abaixo do título e
subtítulo), com microcopy **convidativa e animada** para a pessoa **conversar com o consultor de IA**. O fluxo:

1. **Hero — prompt.** A pessoa digita a intenção (ex.: *"quero cotar meu Onix"*) e envia (Enter / seta).
2. **Modal de pré-cadastro.** Abre um modal **curto** (Nome, E-mail, Telefone/WhatsApp, Placa) +
   **consentimento LGPD**. O prompt digitado é **preservado** para virar a 1ª mensagem do chat.
3. **Verificação por OTP.** Enviamos um código de **5 dígitos** ao e-mail; o modal mostra **5 campos
   sequenciais** + **timer regressivo de 30s** para reenviar. Botão secundário **"Já tem cadastro? Entre"**
   dispara o mesmo fluxo (o usuário só informa o e-mail).
4. **Chat com o consultor de IA.** Autenticado, a pessoa vai ao **chat** (full-page ou painel dedicado),
   que responde ao prompt inicial e conduz a conversa (dúvidas na V1; **cotação multi-turn** na evolução F5).

> O antigo "formulário de cotação no hero" **deixa de existir** — vira o **modal de pré-cadastro** disparado
> pelo prompt. O hero fica limpo: **título, subtítulo e o campo de prompt**.

## Modal de pré-cadastro — contrato de dados (modal → lead)

| Campo (modal) | Campo (Lead) | Obrigatório | Observação |
|---|---|---|---|
| Nome completo | `name` | sim | — |
| E-mail | `email` | sim | **identidade** (verificada por OTP) |
| Telefone/WhatsApp | `phone` | sim | máscara BR |
| Placa do veículo | `vehicle` | sim | (marca/modelo/ano como fallback) |
| Consentimento LGPD | `consent` | sim | checkbox explícito |
| (oculto) `Idempotency-Key` | header | sim | **uuid gerado no client** ao carregar o modal |
| (oculto) origem/UTM | `source` | não | atribuição de campanha (F6) |

> **CEP** e demais dados da cotação são coletados **no chat** (conversa), não no modal — mantendo o
> pré-cadastro curto. *(Nota técnica: enquanto o backend exige `zipcode`, a LP pode enviar um valor
> provisório até a coleta no chat — refino da F5.)*

Envio: `Modal → POST /api/lead (BFF) → POST /leads (ai-service)` → então `POST /api/auth/request-otp`.
Resposta rápida; o enriquecimento (qualificação + CRM + Ads) roda no worker.

## Instrumentação de conversão (eventos)

- `lp_view`, **`prompt_focus`**, **`prompt_submit`** (a pessoa iniciou a conversa), `signup_view`,
  `signup_submit`, `otp_view`, `otp_verified`, `chat_message` (frontend/analytics).
- No submit do pré-cadastro: o ai-service registra `lead_received` e o worker dispara os **eventos de
  conversão** para as plataformas de anúncios (`AdsPort`, com `event_id` estável para dedup).

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
