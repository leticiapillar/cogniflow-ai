# Plano de Execução: `improvements_plan_02` — Abrangência RAG Adaptativa, Estruturação Pedagógica em 2 Estágios e Acessibilidade Cognitiva (TDAH/TEA/Surdos)

> **Objetivo:** Evoluir a recuperação RAG, o pipeline de síntese e estruturação pedagógica do backend e a apresentação visual do frontend do **CogniFlow AI** para produzir mapas mentais profundos, coerentes e cognitivamente acessíveis para estudantes surdos (Português como L2) e neurodivergentes (TDAH e TEA), permitindo testes comparativos entre **Google Gemini** e **Ollama**.

---

## Etapa 1: Seletor Pedagógico de Abrangência no Frontend e Cobertura Estratificada no RAG (`frontend/features/mind-map/` & `backend/app/services/rag_retriever.py`)
- [x] Definir presets pedagógicos de abrangência (`COVERAGE_OPTIONS` em `frontend/features/mind-map/schemas.ts`): **Essencial (5 trechos)**, **Detalhada (10 trechos)**, **Ampla (15 trechos)** e **Completa (20 trechos)**.
- [x] Adicionar o seletor acessível **Abrangência do mapa** (`#study-coverage`) em `MindMapForm` (`frontend/features/mind-map/components/mind-map-form.tsx`) exibindo a contagem total de trechos do PDF ativo e preservando o fluxo de foco por teclado.
- [x] Evoluir o `useGenerateMindMap` (`frontend/features/mind-map/hooks/use-generate-mind-map.ts`) e o `StudyWorkspace` (`frontend/components/study-workspace.tsx`) para gerenciar o estado `topK` selecionado pelo estudante.
- [x] Implementar amostragem estratificada por seção em `RAGRetriever.retrieve_relevant_chunks` (`backend/app/services/rag_retriever.py`): quando `top_k >= 10` e um documento é filtrado, distribuir o orçamento de recuperação ao longo de todo o documento (`get_chunks_by_document`) em ordem canônica (`chunk_index ASC`), garantindo cobertura de início, meio e fim do material.
- [x] Criar testes unitários no frontend (`mind-map-form.test.tsx`, `use-generate-mind-map.test.ts`) e no backend (`test_rag_and_llm_orchestration.py`) validando o seletor e a cobertura estratificada.

## Etapa 2: Passo Intermediário de Síntese e Estruturação Pedagógica (`backend/app/services/pedagogical_structurer.py`)
- [x] Implementar reconstrução de sentenças de PDF (`reflow_pdf_text_into_sentences`) para unir linhas quebradas no meio de frases, proteger abreviações (`Prof.`, `Dr.`, `Ex.`, `et al.`) e filtrar ruídos de metadados/autoria.
- [x] Higienizar rótulos de conceitos (`clean_concept_label`), eliminando preposições/conjunções pendentes no final dos títulos (`"dos seus"`, `"ou"`, `"de"`) e parênteses não fechados.
- [x] Implementar o estruturador em 2 estágios (`build_pedagogical_outline`):
  - **Estágio 1 (Síntese Direta):** Elaboração de uma resposta textual concisa (`direct_synthesis`) respondendo diretamente à consulta do estudante para alimentar o resumo do nó central (`node-root`).
  - **Estágio 2 (Árvore Taxonômica):** Agrupamento dos conceitos extraídos em **Eixos Temáticos de Nível 1 (`category: "topic"`)** (*Definição e Distinção*, *Fundamentos e Arquitetura*, *Evolução Histórica*, *Aplicações e Conteúdos*, ou cabeçalhos reais do PDF) e **Subconceitos, Marcos Cronológicos e Exemplos de Nível 2 (`category: "concept" | "example"`)** com verbos relacionais no idioma da consulta.
- [x] Criar o compilador determinístico (`compile_outline_to_mind_map_dict`) e o normalizador de saídas de LLM (`normalize_llm_mind_map_json`) capaz de converter árvores aninhadas (`branches`/`children`) ou JSONs parciais em grafos `nodes` + `edges` 100% compatíveis com o contrato do React Flow.

## Etapa 3: Engenharia de Prompt em 2 Estágios e Regras Linguísticas para Surdos (L2) e Neurodivergentes (`backend/app/services/prompts.py` & `backend/app/services/llm_provider.py`)
- [x] Injetar o esqueleto estruturado `<PEDAGOGICAL_OUTLINE>` em `build_user_prompt` (`backend/app/services/prompts.py`) antes de `<RETRIEVED_CONTEXT>`, guiando tanto o **Gemini** quanto o **Ollama** com a síntese e os eixos pré-identificados.
- [x] Incluir no `MIND_MAP_SYSTEM_PROMPT` a seção `NEURODIVERGENT (ADHD/ASD) & DEAF (L2) LINGUISTIC ACCESSIBILITY RULES`:
  - **Ordem Direta e Voz Ativa (Surdos / Português L2):** Frases estruturadas em `Sujeito → Verbo → Objeto`, evitando voz passiva e subordinações longas.
  - **Literalidade e Objetividade (TEA):** Linguagem 100% literal e concreta, sem metáforas ou expressões ambíguas.
  - **Baixa Carga de Memória de Trabalho e Clareza de Siglas (TDAH):** Expansão de siglas na primeira menção e ancoragem em exemplos práticos (`category: "example"`).
- [x] Atualizar `GEMINI_MIND_MAP_RESPONSE_SCHEMA` (`backend/app/services/llm_provider.py`) com o campo `"pedagogical_synthesis"` (*Chain-of-Thought* antes de `"nodes"`), priorizar candidatos `gemini-2.5-flash` / `gemini-2.0-flash`, ampliar a janela de geração do `OllamaLLMProvider` (`num_ctx: 8192`, `num_predict: 2500`) e integrar o `ContextGroundedLocalLLMProvider` ao compilador pedagógico.

## Etapa 4: Diferenciação Visual Semântica e Redução de Atenção Dividida no Frontend (`frontend/features/mind-map/` & `frontend/app/globals.css`)
- [x] Implementar mapeamento visual por categoria (`getCategoryMeta` em `frontend/features/mind-map/graph-config.ts` e classes em `frontend/app/globals.css`):
  - **Tema central (`root`):** Indicador e faixa lateral coral (`#ff6b4a`).
  - **Eixo temático (`topic`):** Indicador e faixa lateral azul (`#0284c7`).
  - **Conceito (`concept`):** Indicador e faixa lateral índigo (`#5044d3`).
  - **Exemplo prático (`example`):** Indicador e faixa lateral verde esmeralda (`#059669`).
- [x] Exibir o selo da categoria semântica e uma prévia de 1 linha do resumo (`data.summary`) diretamente nos cartões do grafo (`MindMapNode` em `frontend/features/mind-map/components/mind-map-node.tsx`), reduzindo o *split-attention effect* para estudantes com TDAH.
- [x] Exibir a categoria semântica de cada nó também no painel `ConceptDetails` (`frontend/features/mind-map/components/concept-details.tsx`) e na leitura linear em lista `MindMapOutline` (`frontend/features/mind-map/components/mind-map-outline.tsx`).

## Etapa 5: Validação Automatizada e Testes Comparativos Multi-Provedor (`Ollama` vs. `Gemini`)
- [x] Validar todas as suítes de testes unitários do frontend (`vitest` — 106 testes passando e `eslint` sem alertas) e do backend (`pytest` — suíte de orquestração RAG/LLM, estruturador pedagógico e recall médio de 100% nas 20 apostilas acadêmicas).
- [ ] Executar homologação comparativa na interface web com os provedores **Ollama** e **Google Gemini** utilizando o seletor de abrangência (**Completa — 20 trechos**) sobre o material de estudo.

