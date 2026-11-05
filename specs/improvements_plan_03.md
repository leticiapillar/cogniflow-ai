# Plano de Execução: `improvements_plan_03` — Tutor de Aula para Alunos Neurodivergentes: Mapa Mental por Map-Reduce e Tira-Dúvidas por RAG

> **Objetivo:** Reposicionar o **CogniFlow AI** como um **tutor de aula para alunos neurodivergentes (TDAH e TEA)**. A partir do PDF da aula, a aplicação (1) monta **um mapa mental do material inteiro** usando **map-reduce** e (2) permite que o aluno **faça perguntas sobre suas dúvidas**, respondidas com **RAG** apenas com base no conteúdo do PDF.
>
> **Stack de IA desta versão:** 100% local via **Ollama** — LLM com **3B de parâmetros** (`llama3.2:3b`) e embeddings **`bge-m3`** (multilíngue, melhor desempenho em português).

---

## Motivação

A geração atual do mapa mental via RAG é incoerente com a tarefa: o mapa é um **resumo global** do material, mas o RAG recupera apenas os `top_k` trechos mais parecidos com uma pergunta. Resultado: mapas que mudam conforme a frase digitada, seções importantes omitidas e heurísticas de compensação (expansão de vizinhos, amostragem estratificada) no `rag_retriever.py`.

| Tarefa | Natureza | Técnica |
|---|---|---|
| Mapa mental da aula | Resumo global, independente de pergunta, gerado uma vez por PDF | **Map-reduce** |
| Dúvidas do aluno | Pergunta pontual sobre um trecho do material | **RAG** |

## Decisões de Escopo

- **Público:** apenas alunos neurodivergentes (**TDAH** e **TEA**). O público surdo (Português L2) fica para uma versão futura — as regras de acessibilidade passam a ser organizadas em **perfis** para permitir adicioná-lo depois sem reescrever os prompts.
- **Provedores:** apenas **Ollama**. O **Gemini** deixa de ser suportado nesta versão, mas as interfaces `BaseLLMProvider` e `BaseEmbeddingProvider` são mantidas para reintroduzi-lo no futuro.
- **LLM:** `llama3.2:3b` como padrão (configurável). `qwen2.5:3b` será avaliado como alternativa na Etapa 7 (bom desempenho em JSON estruturado e multilíngue).
- **Embeddings:** `bge-m3` → **1024 dimensões** (o atual é 768), exige recriar a tabela de vetores.
- **Estrutura do mapa:** árvore pura (sem ligações cruzadas entre ramos), 4 categorias atuais (`root`, `topic`, `concept`, `example`) e **exibição progressiva** (abre com tema + eixos; expande ao clicar). Menos estímulo visual e mais previsibilidade para TDAH/TEA.
- **Sem substitutos determinísticos para a IA:** o provedor de embeddings por *hashing* e a geração de mapa por heurística (`ContextGroundedLocalLLMProvider`, `build_pedagogical_outline`) são **removidos da aplicação**. Quando a IA falha, a aplicação repete a tentativa e, se ainda falhar, **informa a falha de forma clara e previsível** em vez de entregar um resultado de qualidade inferior como se fosse da IA.
- **Fora do escopo:** público surdo, Gemini, streaming de respostas, busca híbrida (vetorial + full-text), múltiplos PDFs por sessão de estudo.

## Princípio: a IA gera, o código garante

| Responsabilidade | Quem faz |
|---|---|
| Extrair conceitos, definir eixos, escrever sínteses e respostas | **LLM** (`llama3.2:3b`) |
| Representar significado para busca e deduplicação | **Embeddings** (`bge-m3`) |
| Limpar o texto do PDF e dividir em seções | Código (pré-processamento) |
| Fundir conceitos duplicados (similaridade entre vetores `bge-m3`) | Código sobre a saída da IA |
| Validar schema, limites de carga cognitiva e citações | Código (pós-processamento) |
| Layout do grafo e sanitização contra *prompt injection* | Código |

> **Por que remover os substitutos:** os vetores por *hashing* não são comparáveis aos do `bge-m3` — misturá-los na mesma tabela torna trechos invisíveis para a busca, sem nenhum erro aparente. A heurística de mapa classifica eixos por palavras-chave de um domínio fixo (IA) e transforma frases isoladas em conceitos. Em ambos os casos o aluno recebe um resultado pior acreditando que ele veio da IA — o oposto da previsibilidade que alunos com TEA e TDAH precisam.

---

## Estrutura Pedagógica do Mapa Mental

Fundamentos: organizadores prévios de Ausubel (do geral para o específico), mapas conceituais de Novak (cada aresta forma a proposição *conceito → verbo → conceito*) e teoria da carga cognitiva (3 a 5 itens por nível).

```
Nível 0  root     Tema central da aula (título do PDF)
                  └─ síntese: 2–3 frases — "o que é" e "por que importa"
Nível 1  topic    Eixos de estudo (3 a 5), NUMERADOS na ordem de leitura sugerida
                  └─ derivados das seções do próprio documento (sem categorias fixas)
Nível 2  concept  Conceitos-chave de cada eixo (até 5 por eixo)
                  └─ definição literal em 1–2 frases curtas
Nível 3  example  Exemplo concreto do material (até 2 por conceito, opcional)
```

**Campos de cada nó:** `label` (1 a 6 palavras), `summary` (1 a 2 frases), `category`, `order` (sequência de estudo), `acronyms` (siglas expandidas), `source_chunks` (índices dos trechos de origem — evidência e ponte para o tira-dúvidas).

**Vocabulário controlado de relações** (exibido como verbo em português):

| Tipo | Verbo exibido |
|---|---|
| `has_part` | "divide-se em" / "contém" |
| `is_a` | "é um tipo de" |
| `causes` | "produz" / "causa" |
| `depends_on` | "depende de" |
| `precedes` | "vem antes de" |
| `contrasts` | "diferencia-se de" |
| `exemplified_by` | "exemplificado por" |

## Perfil de Acessibilidade Neurodivergente (TDAH/TEA)

Aplicado a todo texto gerado (mapa e respostas do tutor):

- **TEA — literalidade e previsibilidade:** linguagem 100% literal e concreta; sem metáforas, ironia, expressões idiomáticas ou perguntas retóricas; mesma estrutura de resposta sempre; mesmo verbo para o mesmo tipo de relação.
- **TDAH — baixa carga de memória de trabalho:** frases curtas (até ~20 palavras) em ordem direta; uma ideia por frase; resposta principal primeiro; siglas expandidas na primeira menção; no máximo 3 a 5 itens por lista; um exemplo concreto sempre que o material oferecer.
- **Ambos:** termos técnicos definidos na primeira ocorrência; nenhuma informação fora do material da aula.

---

## Etapa 1: Infraestrutura e Configuração (`docker-compose.yml`, `backend/.env.example`, `backend/app/core/config.py`)
- [x] Atualizar o serviço `ollama_init` para baixar `bge-m3` e `llama3.2:3b` por padrão.
- [x] Atualizar `.env.example` e `Settings`: `EMBEDDING_PROVIDER="ollama"`, `LLM_PROVIDER="ollama"`, `OLLAMA_EMBEDDING_MODEL="bge-m3"`, `OLLAMA_LLM_MODEL="llama3.2:3b"`, `EMBEDDING_DIMENSION=1024`, `OLLAMA_NUM_CTX=8192`.
- [x] Remover a opção `"local"` de `EMBEDDING_PROVIDER` e `LLM_PROVIDER` (e o padrão `"local"` em `Settings`): os únicos provedores válidos nesta versão são `ollama`; valores desconhecidos falham na inicialização.
- [x] Remover as variáveis `GEMINI_*` do `.env.example` (mantê-las opcionais em `Settings`, sem uso nesta versão) e corrigir a lista de modelos-fallback do `GeminiLLMProvider`, que contém nomes inexistentes.
- [x] **Verificação de prontidão do Ollama** na inicialização e em `GET /api/health`: servidor acessível, modelos `bge-m3` e `llama3.2:3b` presentes em `/api/tags` e vetor de teste com 1024 dimensões. O health passa a retornar `status: "degraded"` com o motivo quando algum item falhar.
- [x] Documentar o requisito de hardware (≈ 4 GB de RAM livres para `llama3.2:3b` + `bge-m3`) e a variável `OLLAMA_NUM_PARALLEL` (o Ollama processa requisições em série por padrão).

## Etapa 2: Embeddings `bge-m3` e Novo Modelo de Dados (`backend/app/services/embeddings.py`, `backend/app/repositories/`)
- [x] Extrair a interface `BaseEmbeddingProvider` com a implementação `OllamaEmbeddingProvider`, mantendo um ponto de extensão para Gemini.
- [x] **Remover `_compute_deterministic_embedding` e o fallback silencioso** de `embeddings.py`: misturar vetores de espaços diferentes na mesma tabela corrompe a busca. O `FakeEmbeddingProvider` para testes passa a viver em `backend/tests/fakes/`, injetado por fixture — a aplicação não consegue selecioná-lo.
- [x] Usar o endpoint `/api/embed` do Ollama com **lote** (`input: [..]`) e `httpx.AsyncClient` — elimina o bloqueio do event loop causado pelo `httpx.Client` síncrono atual.
- [x] **Repetição com *backoff*** (até 3 tentativas) apenas para erros transitórios — timeout, conexão recusada, HTTP 5xx. Esgotadas as tentativas, lançar `EmbeddingProviderError`, convertido em HTTP 503 com mensagem compreensível.
- [x] Validar a dimensão de todo vetor retornado (`== EMBEDDING_DIMENSION`) antes de persistir.
- [x] **Ingestão tudo-ou-nada:** gerar todos os vetores antes de abrir a transação de escrita, de modo que uma falha não deixe o documento parcialmente vetorizado.
- [x] Criar a tabela `documents` (`id`, `name`, `sha256`, `page_count`, `embedding_model`, `created_at`) e vincular `document_chunks` por `document_id`.
- [x] Migrar `document_chunks.embedding` para `Vector(1024)` e adicionar as colunas `section_title`, `page_start` e `page_end` (para citar "página N" nas respostas). Como `create_all` não altera tabelas existentes, criar o script `backend/scripts/migrate_03.sql` (drop + recriação) e documentar a necessidade de reingerir os PDFs.
- [x] Criar índice **HNSW** (`vector_cosine_ops`) em `document_chunks.embedding`.
- [x] Preservar o mapeamento página → texto no `pdf_parser.py` e propagá-lo pelo chunking.
- [x] Recusar consultas a documentos ingeridos com um `embedding_model` diferente do configurado (orientar reingestão).

## Etapa 3: Mapa Mental por Map-Reduce (`backend/app/services/mind_map/`)
- [x] **Unidade de trabalho = seção** (saída do `MarkdownHeaderTextSplitter`), agrupando seções vizinhas pequenas e dividindo seções grandes até ~6.000 caracteres para caber no `num_ctx` de 8192 tokens do modelo 3B.
- [x] **Map (1 chamada por seção):** extrair JSON com conceitos (`label`, `summary`, `acronyms`, `examples`, `source_chunks`). *Ajuste na implementação:* sem relações internas da seção — com o mapa em árvore pura (sem ligações cruzadas), elas não seriam usadas, e omiti-las reduz a carga sobre o modelo de 3B. Usar **structured outputs do Ollama** (`format` recebendo o JSON Schema gerado do modelo Pydantic), essencial para a confiabilidade de um modelo de 3B.
- [x] **Reduce 1 (determinístico):** fundir conceitos duplicados entre seções por similaridade de embeddings `bge-m3` de `label + summary` (limiar inicial 0,85, calibrado nos testes), unindo `source_chunks` e preservando a ordem de aparição.
- [x] **Reduce 2 (LLM):** a partir da lista consolidada, definir 3 a 5 eixos numerados em ordem de estudo, selecionar até 5 conceitos por eixo, atribuir o tipo de relação do vocabulário controlado e escrever a síntese do `root`. Se a entrada exceder o orçamento de contexto, aplicar **redução hierárquica** (reduzir por grupos de seções e depois consolidar).
- [x] **Repetição com correção:** quando a saída de uma chamada (Map ou Reduce) falhar na validação, repetir até 2 vezes incluindo no prompt o erro encontrado (ex.: *"o campo `source_chunks` está ausente no conceito 3"*). Erros transitórios do Ollama seguem a mesma política de *backoff* da Etapa 2.
- [x] **Falha parcial explícita (sem heurística):** se uma seção continuar falhando na etapa Map, o mapa é montado sem ela, com `status: "partial"` e a lista `failed_sections` (`section_title`, `reason`). Se o Reduce falhar, o mapa fica `failed`. Endpoint `POST /api/documents/{id}/mind-map/sections/{section_index}/retry` para reprocessar apenas a seção afetada.
- [x] **Refatorar o `pedagogical_structurer.py`**, mantendo apenas pré e pós-processamento, em `backend/app/services/text_processing.py`:
  - **Manter:** `reflow_pdf_text_into_sentences` e o filtro de metadados/autoria (limpeza do texto **antes** da IA); `clean_concept_label` (remoção de preposições pendentes nos rótulos **depois** da IA).
  - **Remover:** `_classify_thematic_axis`, `derive_concept_from_sentence`, `build_pedagogical_outline`, `compile_outline_to_mind_map_dict`, `format_pedagogical_outline_for_prompt` e os dataclasses do outline; reduzir `normalize_llm_mind_map_json` ao reparo ainda necessário com *structured outputs*.
- [x] Remover o `ContextGroundedLocalLLMProvider`, todos os fallbacks para ele em `llm_provider.py` e `generate_mind_map.py`, e o bloco `<PEDAGOGICAL_OUTLINE>` do prompt (no map-reduce ele ancora o LLM em eixos escolhidos por palavra-chave).
- [x] **Validação:** estender o `output_validator.py` — tipos de relação dentro do vocabulário controlado; todo `source_chunks` deve existir no documento (verificação anti-alucinação); limites de 3–5 eixos e até 5 conceitos por eixo; árvore sem ciclos e com nó raiz único.
- [x] **Execução assíncrona e persistência:** gerar o mapa em segundo plano após a ingestão (`BackgroundTasks`) e salvar na tabela `mind_maps` (`document_id`, `status`, `progress`, `payload JSONB`, `model`, `error`). Reutilizar o mapa salvo quando o `sha256` do PDF não mudar.
- [x] **API:** `GET /api/documents/{id}/mind-map` retornando `status` (`pending` | `processing` | `ready` | `partial` | `failed`), `progress` (ex.: "seção 3 de 12"), `failed_sections` e o grafo quando pronto; `POST /api/documents/{id}/mind-map/regenerate`.
- [x] Remover `query`/`top_k` da geração do mapa e aposentar o `POST /api/generate-map` (manter por uma versão retornando HTTP 410 com orientação).

## Etapa 4: Tutor Tira-Dúvidas por RAG (`backend/app/services/tutor/`, `backend/app/routers/tutor.py`)
- [x] **API:** `POST /api/documents/{id}/ask` com `question`, `history` opcional (últimas 4 trocas) e `node_id` opcional (dúvida a partir de um conceito do mapa).
- [x] **Recuperação:** busca vetorial `top_k=5` com expansão de vizinhos (`± 1`), restrita ao documento. Quando há `node_id`, priorizar os `source_chunks` do nó. Remover a amostragem estratificada (não se aplica a perguntas pontuais).
- [x] **Reescrita da pergunta com histórico:** quando houver `history`, reescrever a pergunta em forma autônoma antes da busca (ex.: "e ela depende de quê?" → "de que a fase clara depende?").
- [x] **Limiar de relevância:** se a melhor similaridade ficar abaixo do limiar calibrado, responder sem chamar o LLM: *"Não encontrei isso no material da aula."* e sugerir 2 conceitos do mapa relacionados.
- [x] **Formato da resposta (perfil neurodivergente), via structured outputs:**
  - `answer`: resposta direta em 1 a 2 frases;
  - `key_points`: até 3 tópicos curtos;
  - `example`: um exemplo do material (opcional);
  - `terms`: termos técnicos usados, com definição;
  - `citations`: `chunk_index`, `page`, `section_title` e trecho curto;
  - `found_in_material`: booleano.
- [x] **Segurança:** sanitizar a pergunta (reaproveitar `sanitize_text_input`), delimitar os trechos recuperados como dados no prompt e validar que toda citação referencia um trecho efetivamente recuperado.
- [x] **Falha explícita:** saída inválida → até 2 novas tentativas com o erro de validação no prompt; persistindo a falha ou com o Ollama indisponível, HTTP 503 com a mensagem *"O tutor está indisponível no momento. Tente novamente em instantes."* — nunca uma resposta montada sem o LLM.

## Etapa 5: Prompts por Perfil de Acessibilidade (`backend/app/services/prompts/`)
- [x] Reorganizar `prompts.py` em blocos combináveis: **regras de grounding**, **perfil de acessibilidade** (`neurodivergent`) e **contrato de saída** por tarefa (`map_section`, `reduce_map`, `tutor_answer`, `rewrite_question`).
- [x] Remover as regras específicas para surdos (Português L2) e as referências a esse público, mantendo o ponto de extensão `AccessibilityProfile` para o futuro.
- [x] Escrever os prompts em **português** e com exemplos curtos de entrada/saída (*few-shot*) — modelos de 3B seguem melhor instruções no idioma do conteúdo e com exemplos concretos.

## Etapa 6: Frontend do Tutor (`frontend/features/`)
- [x] **Fluxo:** upload do PDF → indicador de progresso da geração do mapa (polling do `status`/`progress`, com mensagem previsível de etapa) → mapa pronto → tira-dúvidas habilitado.
- [x] **Prontidão do serviço:** consultar `GET /api/health` ao carregar a página; com `status: "degraded"`, desabilitar o upload e exibir *"O serviço de IA está iniciando ou indisponível."* com botão para verificar novamente.
- [x] **Mapa parcial:** com `status: "partial"`, exibir aviso discreto e literal listando as seções não processadas, cada uma com a ação **"Tentar de novo"**; com `failed`, mensagem clara e ação **"Gerar novamente"**.
- [x] Remover o formulário de tema (`MindMapForm`) e o seletor de abrangência (`COVERAGE_OPTIONS`) da geração do mapa.
- [x] **Exibição progressiva** no `MindMapViewer` e no `MindMapOutline`: abrir com `root` + eixos numerados; expandir/recolher eixos por clique e teclado (`Enter`/`Espaço`), preservando o estado ao alternar Mapa ↔ Lista.
- [x] Nova feature `frontend/features/tutor/`: painel de perguntas com histórico da sessão, resposta no formato estruturado (resposta → tópicos → exemplo → termos), citações com página e campo de pergunta com limite de caracteres e foco gerenciado.
- [x] No `ConceptDetails`, adicionar a ação **"Tirar dúvida sobre este conceito"**, que abre o tutor com `node_id` preenchido.
- [x] Atualizar schemas Zod, tipos e testes (Vitest) e os fluxos E2E com axe-core (Playwright).

## Etapa 7: Validação, Avaliação e Documentação
- [ ] **Separar testes de fluxo e avaliação de qualidade:**
  - **Testes rápidos** (`pytest`, padrão): provedores falsos em `backend/tests/fakes/` (`FakeEmbeddingProvider`, `FakeLLMProvider` com respostas fixas, incluindo respostas inválidas para exercitar repetição e `partial`) cobrindo map, reduce, deduplicação, validador, limiar do tutor e tratamento de falhas; **integração** com Testcontainers + pgvector em 1024 dimensões e HNSW. Esses testes verificam o encadeamento, **não** a qualidade pedagógica.
  - **Avaliação com IA real** (`pytest -m llm`, exige Ollama com os modelos baixados): suíte lenta e separada, executada antes de cada entrega.
- [ ] Migrar o `test_academic_evaluation_suite.py` para a suíte `llm`. **Observação:** o recall médio de 100% registrado no `improvements_plan_02` foi medido com o provedor heurístico (configuração padrão `local`) sobre apostilas no formato `Conceito: explicação` — exatamente o padrão que a heurística extrai. A linha de base de qualidade precisa ser medida novamente com o LLM.
- [ ] **Avaliação do mapa:** recall de entidades sobre o documento inteiro (`evaluation_metrics.py`), percentual de nós com `source_chunks` válidos, taxa de seções `partial` e conformidade com os limites de carga cognitiva.
- [ ] **Avaliação do tutor:** conjunto de perguntas sobre `fotossintese-texto-selecionavel.pdf` — 10 respondíveis pelo material (citação correta) e 5 fora do material (devem retornar `found_in_material: false`).
- [ ] **Comparativo de modelos 3B:** `llama3.2:3b` vs. `qwen2.5:3b` — taxa de JSON válido na primeira tentativa, recall, aderência ao perfil de acessibilidade e latência (tempo total do mapa e por resposta).
- [ ] Atualizar o `README.md` e o `docs/arquitetura-frontend.md`: novo posicionamento (tutor para neurodivergentes), stack Ollama, migração de banco e reingestão dos PDFs.
