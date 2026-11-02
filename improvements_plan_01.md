# Plano de Execução: `improvements_plan_01` — Coerência Pedagógica e Hierárquica de Mapas Mentais

> **Objetivo:** Evoluir o pipeline RAG e a orquestração LLM do backend do **CogniFlow AI** para produzir mapas mentais com estrutura taxonômica multi-nível (Tema Central → Eixos Temáticos → Subconceitos, Marcos e Exemplos), preservando a coerência narrativa e cronológica do material acadêmico e garantindo compatibilidade integral com o contrato JSON do frontend (`React Flow` + `Dagre`) e com a suíte de testes automatizados.

---

## Etapa 1: Chunking Semântico com Preservação de Contexto de Seção (`backend/app/services/chunking.py`)
- [x] Extrair e identificar o título/cabeçalho de cada seção acadêmica durante o `split_text_by_headers`.
- [x] Ao subdividir seções longas via `RecursiveCharacterTextSplitter`, injetar o cabeçalho da seção pai no início dos sub-chunks subsequentes (evitando sub-chunks "órfãos" sem referência ao eixo temático, como *Definição*, *Fundamentos* ou *Evolução Histórica*).
- [x] Criar testes unitários garantindo que sub-chunks de seções extensas preservem o contexto do título original.

## Etapa 2: Recuperação RAG com Expansão de Janela e Ordem Canônica (`backend/app/repositories/document_repository.py` & `backend/app/services/rag_retriever.py`)
- [x] Implementar busca de vizinhança contextual (*Context Window Expansion*): a partir dos `top_k` trechos mais similares por distância de cosseno no `pgvector`, incluir chunks adjacentes (`chunk_index - 1` e `chunk_index + 1` do mesmo documento) ou cobrir integralmente documentos compactos dentro de um limite seguro de contexto.
- [x] Reordenar os chunks recuperados em ordem crescente de `chunk_index` (`chunk_index ASC`) antes de enviá-los ao prompt do LLM, preservando a progressão didática e a linha do tempo do material original.
- [x] Adicionar testes validando a desduplicação e a ordenação canônica dos chunks recuperados.

## Etapa 3: Engenharia de Prompt Pedagógica Multi-Nível (`backend/app/services/prompts.py`)
- [x] Refinar o `MIND_MAP_SYSTEM_PROMPT` (mantido integralmente em inglês e com todas as garantias de grounding e idioma) para exigir uma **árvore conceitual hierárquica em 3 níveis**:
  - **Nível 0 (`category: "root"`, `type: "input"`):** Nó raiz único representando exatamente o `<USER_QUERY>`.
  - **Nível 1 (`category: "topic"`, `type: "default"`):** De 2 a 5 pilares/eixos estruturantes extraídos do material (ex.: *Definição e Distinção*, *Fundamentos / Pilares*, *Evolução Histórica*, *Aplicações / Exemplos*).
  - **Nível 2 (`category: "concept"` ou `"example"`, `type: "default"`):** Subconceitos específicos, comparações, marcos cronológicos ou exemplos concretos conectados ao seu respectivo eixo de Nível 1.
- [x] Determinar o uso de rótulos de arestas (`edges.label`) com verbos semânticos explicativos e concisos no idioma da consulta (ex.: *"divide-se em"*, *"diferencia-se por"*, *"exemplificado por"*, *"evoluiu em"*, *"composto por"*), evitando rótulos genéricos repetitivos.
- [x] Enriquecer a formatação dos blocos no `build_user_prompt` indicando a posição sequencial de cada trecho do documento.

## Etapa 4: Structured Outputs (`responseSchema`) no Gemini e Evolução do Provedor Local (`backend/app/services/llm_provider.py`)
- [x] Configurar `responseSchema` nativo na chamada `generateContent` do `GeminiLLMProvider` (além de `responseMimeType="application/json"`), forçando a API do Gemini a respeitar estritamente a estrutura de `topic`, `nodes` (`id`, `type`, `data.label`, `data.summary`, `data.category`, `position`) e `edges` (`id`, `source`, `target`, `label`, `animated`).
- [x] Aprimorar também o `ContextGroundedLocalLLMProvider` para organizar os conceitos extraídos em agrupamentos hierárquicos (`root -> topic -> concept`) quando houver múltiplos blocos/seções de contexto.
- [x] Adicionar testes unitários verificando o payload de `responseSchema` do Gemini e a hierarquia gerada.

## Etapa 5: Validação de Conectividade de Grafo e Homologação (`backend/app/services/output_validator.py` & `backend/tests/`)
- [ ] Evoluir o `validate_and_parse_mind_map_json` para verificar conectividade a partir da raiz: caso o LLM gere algum nó válido porém desconectado (órfão sem aresta de entrada), vinculá-lo automaticamente ao nó `root` para impedir "ilhas" soltas no canvas do React Flow.
- [ ] Garantir unicidade de identificadores de arestas (`edge.id`) em conformidade com a validação `superRefine` do frontend (`schemas.ts`).
- [ ] Executar a suíte de testes automatizados (`pytest`) e validar um teste real fim-a-fim com o **Gemini** (`gemini-3.8-flash` + `gemini-embedding-001`) gerando um mapa mental hierárquico a partir dos PDFs do projeto.

