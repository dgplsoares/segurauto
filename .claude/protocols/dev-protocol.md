# Protocolo de Desenvolvimento — SegurAuto

> Protocolo próprio de engenharia orientada a especificação (SDD). Doc operacional: o "o que
> construir" está em `.claude/docs/analise-orbitus.md` e `.claude/plan/plano-execucao.md`.

## 1. Workflow obrigatório

```
1. ANÁLISE     - entender o pedido, mapear impacto e riscos
2. SOLUÇÕES    - opções com prós e contras quando há escolha relevante
3. PLANO       - atualizar .claude/plan/plano-execucao.md (fases, checklist)
4. APROVAÇÃO   - validar o plano antes de codar
5. DECISÕES    - registrar o não trivial em .claude/decisions/DECISIONS.md (DEC-ORB-00X)
6. IMPLEMENTAR - só então codar, bloco a bloco, marcando [x]
7. VERIFICAR   - testes (mock + real) + docker compose up; honestidade sobre pronto vs pendente
```

Guardrail: nunca sair implementando direto, mesmo em tarefa "óbvia".

## 2. Guiado por testes (mock + real)

Os testes são a rede de segurança e o critério de aceite de cada fase, tecidos junto com o código
(não depois):

- **unit** — domínio puro, sem infra (fakes injetados; sem DB/HTTP).
- **integração** — com **adapters fake** + LLM **stub** determinístico; é o **gate de CI** (sem segredos).
- **real** — opt-in por `.env` (OpenAI/CRM reais); exercita o mesmo contrato via o seam de porta/adapter,
  **sem mudar código**.

## 3. Decisões (rastreabilidade)

Cada decisão não trivial vira um registro em `DECISIONS.md`:

```
DEC-ORB-00X — <título>
Contexto / Opções / Escolha / Trade-off
```

Alimenta a seção de "decisões de arquitetura" do README/entrega.

## 4. Reanálise pré-fase e descobertas

Nenhum plano sobrevive intacto ao contato com o código. Para capturar as descobertas com contexto fresco:

- **ANTES de cada fase:** reanálise curta e proporcional — reler a parte relevante da análise e dos
  testes daquela fase; concatenar o que a fase anterior entregou com o que a próxima exige. Saída:
  mini-roadmap de 3 a 5 itens com gaps e riscos atualizados.
- **DEPOIS de cada fase:** registrar as descobertas (o que mudou vs. o plano, gaps achados, decisões
  tomadas) em `.claude/plan/diario-de-fases.md`. Decisões formais vão para `DECISIONS.md`.
- Atualizar o `plano-execucao.md` se a reanálise mudar o escopo da fase.

Princípio: "plano aprovado" ≠ "cada fase aprovada". Cada fase tem seu micro-ciclo de análise.

## 5. Subagentes (rigor proporcional à complexidade)

- Fase simples e de contrato claro: análise direta.
- Fase incerta ou de superfície ampla (ex.: pipeline RAG + LangGraph): subagentes de
  exploração/planejamento em paralelo quando as frentes são independentes.
- Correção crítica (idempotência, atomicidade da outbox, escopo de segurança do agente):
  somar verificação adversarial (um subagente tentando refutar a solução).

Registrar no diário quando uma fase foi analisada com subagentes.

## 6. Memória persistente (Engram)

- Sempre `project="orbitus"` explícito em `mem_save`, `mem_search`, `mem_context`.
- Salvar proativamente: decisões de arquitetura, padrões, bugs com causa raiz, aprendizados.

## 7. Git & CI/CD

- Commits pequenos ao fim de cada fase ou bloco, incluindo os docs de processo (`CLAUDE.md` + `.claude/`).
- Mensagens semânticas que refletem o processo (ex.: `feat(fase-3): qualification_agent + RAG`).
- Nada destrutivo (`reset --hard`, `push --force`) nem `--no-verify` sem aprovação.
- **Auditoria antes de publicar:** grep de segredos/tokens e de referências a outros projetos — o repo é
  público e **neutro**.
- **CI/CD (V1+):** push na `main` passa pelo **CI** (gate, sem segredos); verde, dispara o **deploy
  automático em produção** (`deploy.yml`, runner self-hosted). Modelo **dev local → `main` → prod remoto**
  (sem branch de homolog separada) — detalhes em [`deploy/ci-cd.md`](../../deploy/ci-cd.md).

## 8. Princípios

- Correção e clareza antes de completude (right-sizing, sem gold-plating).
- Documentar o "porquê", não o "o quê".
- Honestidade de engenharia: assumir limites e trade-offs, não inflar.
- Manter a app funcionando a cada fase (fatias verificáveis, não big-bang).
- Todo efeito externo atrás de porta, trocável por real sem tocar no domínio.
- **Este repositório não referencia outros projetos/empresas** — padrões descritos de forma neutra.
