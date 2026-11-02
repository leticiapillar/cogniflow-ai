# CogniFlow AI

**Traduzindo Texto Denso em Aprendizado Visual**

O **CogniFlow AI** é uma plataforma educacional assistiva que utiliza **RAG (Retrieval-Augmented Generation)** e **IA Generativa** para converter materiais acadêmicos densos (PDFs, apostilas e transcrições) em mapas mentais visuais estruturados, reduzindo a sobrecarga cognitiva para estudantes surdos (Português como L2) e neurodivergentes (TDAH/TEA).

![Interface do CogniFlow AI](docs/cogniflow-interface.png)

---

## Principais Recursos Pedagógicos e de Acessibilidade

- **Estruturação Pedagógica em 2 Estágios**:
  1. **Síntese Direta**: Responde diretamente à dúvida ou tema pesquisado no nó central (`root`).
  2. **Árvore Taxonômica Multi-Nível**: Organiza o conteúdo em **Tema Central (`root`) → Eixos Temáticos (`topic`) → Conceitos (`concept`) e Exemplos Práticos (`example`)**, com arestas rotuladas por verbos semânticos explicativos.
- **Abrangência RAG Adaptativa (`top_k`)**: Seletor pedagógico de cobertura do material (**Essencial — 5 trechos**, **Detalhada — 10 trechos**, **Ampla — 15 trechos** e **Completa — 20 trechos**), utilizando expansão de janela de contexto e amostragem estratificada por seção em ordem canônica (`chunk_index ASC`).
- **Acessibilidade Linguística e Cognitiva (Surdos, TDAH e TEA)**:
  - **Surdos (Português L2)**: Frases em ordem direta (`Sujeito → Verbo → Objeto`) e voz ativa, evitando subordinações longas.
  - **TEA**: Linguagem 100% literal e objetiva, sem metáforas ou ambiguidades.
  - **TDAH**: Expansão de siglas na primeira menção, diferenciação visual semântica por cores/categorias e prévia do resumo diretamente nos cartões do grafo para reduzir a atenção dividida (*split-attention effect*).
- **Alternância Visual / Textual sem Perda de Estado**: Transição imediata entre o **Mapa** interativo (React Flow + layout automático Dagre) e a visualização em **Lista** estruturada (acessível para leitores de tela e navegação integral por teclado), preservando posições, zoom e nó selecionado.
- **Arquitetura Multi-Provedor de IA**: Suporte intercambiável via configuração (`.env`) para execução determinística **Local** (sem chave externa), **Ollama** (modelos locais abertos com privacidade LGPD) ou **Google Gemini** (`responseSchema` estruturado).

---

## Arquitetura do Projeto

```text
cogniflow-ai/
├── docker-compose.yml                        # PostgreSQL 16 (pgvector) + Ollama + pull automático de modelos
├── Proposta_Projeto_CogniFlow_AI.pdf         # PDF da proposta do projeto para testes e demonstração
├── fotossintese-texto-selecionavel.pdf       # PDF didático adicional para testes de estudo
├── docs/                                     # Documentação de arquitetura e assets visuais
│   ├── arquitetura-frontend.md               # Detalhamento da estrutura do frontend
│   └── cogniflow-interface.png               # Captura da interface do CogniFlow AI
├── specs/                                    # Planos de execução e evolução técnica/pedagógica
│   ├── execution_plan.md                     # Plano de execução original dividido em 5 Sprints
│   ├── improvements_plan_01.md               # Coerência pedagógica e hierárquica de mapas mentais
│   └── improvements_plan_02.md               # Abrangência RAG adaptativa e acessibilidade cognitiva
├── backend/                                  # API Orquestradora (Python + FastAPI + Clean Architecture)
│   ├── app/
│   │   ├── core/                             # Configurações (Pydantic Settings), logs e conexão assíncrona DB
│   │   ├── repositories/                     # Persistência e busca por similaridade vetorial (pgvector)
│   │   ├── routers/                          # Endpoints REST (/api/health, /api/documents, /api/generate-map)
│   │   ├── schemas/                          # Contratos estritos de entrada/saída (Pydantic)
│   │   ├── services/                         # PDF parser, chunking, estruturação pedagógica, RAG, LLM e métricas
│   │   └── use_cases/                        # Regras de negócio da aplicação
│   ├── scripts/
│   │   ├── init_db.sql                       # Script de inicialização da extensão vector
│   │   └── demo_pitch.py                     # Script de demonstração ao vivo para o Pitch
│   └── tests/                                # Suíte de testes automatizados (PyTest + Testcontainers)
└── frontend/                                 # Next.js 16 + TypeScript + Tailwind + React Flow
    ├── app/                                  # App Router, layout e estilos globais
    ├── components/                           # Composição do workspace e componentes compartilhados
    ├── features/                             # Módulos documents e mind-map (componentes, hooks, schemas e serviços)
    ├── services/                             # Cliente HTTP compartilhado
    ├── test-utils/                           # Utilitários para testes de integração com a API real
    └── e2e/                                  # Playwright: interação, acessibilidade (axe-core) e fluxo real
```

Consulte a [estrutura do frontend](docs/arquitetura-frontend.md) para conhecer em detalhes a organização das páginas, componentes, features, serviços e testes.

---

## Pré-requisitos

- **Docker** e **Docker Compose** (para o banco PostgreSQL + `pgvector`, servidor `Ollama` e testes com Testcontainers)
- **Python 3.11+** e `pip`
- **Node.js 20.19+** na linha 20, **22.12+** na linha 22 ou **24+**, e `npm`

---

## 1. Subindo a Infraestrutura com Docker Compose (`pgvector` + `Ollama`)

Na raiz do projeto, inicie os serviços de infraestrutura:

```bash
docker compose up -d
```

Esse comando provisiona:
- **`cogniflow_pgvector`** (`pgvector/pgvector:pg16` na porta `5432`): banco de dados PostgreSQL 16 com a extensão `vector` inicializada automaticamente.
- **`cogniflow_ollama`** (`ollama/ollama:latest` na porta `11434`): servidor local para execução de LLMs e embeddings abertos.
- **`cogniflow_ollama_init`**: container auxiliar que baixa automaticamente os modelos padrão (`nomic-embed-text` e `llama3.2:1b`) assim que o serviço `ollama` fica saudável.

> **Dica:** Caso deseje subir **apenas o banco de dados** (por exemplo, para rodar com os provedores `local` ou `gemini` sem baixar modelos do Ollama), execute:
> ```bash
> docker compose up -d postgres
> ```

Para verificar o status dos containers e acompanhar o download inicial dos modelos do Ollama:

```bash
docker compose ps
docker compose logs -f ollama_init
```

---

## 2. Configurando e Rodando o Backend (FastAPI)

### 2.1. Configurar Variáveis de Ambiente

Entre no diretório `backend/` e crie o arquivo `.env` a partir do template `.env.example`:

```bash
cd backend
cp .env.example .env
```

> **Configuração de Provedores de IA (`EMBEDDING_PROVIDER` e `LLM_PROVIDER`):**
> - **Modo Local Determinístico (Padrão em `.env.example`):** `EMBEDDING_PROVIDER="local"` e `LLM_PROVIDER="local"` permitem rodar toda a aplicação localmente de forma instantânea, sem chave de API externa nem download de modelos pesados.
> - **Modo Ollama (IA Generativa Local / Privacidade LGPD):** Altere para `EMBEDDING_PROVIDER="ollama"` e `LLM_PROVIDER="ollama"`, mantendo `OLLAMA_BASE_URL="http://localhost:11434"`, `OLLAMA_EMBEDDING_MODEL="nomic-embed-text"` e `OLLAMA_LLM_MODEL="llama3.2:1b"`.
> - **Modo Google Gemini (Nuvem com Structured Outputs):** Altere para `EMBEDDING_PROVIDER="gemini"` e `LLM_PROVIDER="gemini"`, e preencha `GEMINI_API_KEY="sua_chave"`.

### 2.2. Criar Ambiente Virtual e Instalar Dependências

Caso o ambiente `.venv` ainda não exista:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

*(Caso já exista o `.venv` criado no diretório `backend/`, basta ativá-lo com `source .venv/bin/activate` ou executar diretamente `./.venv/bin/uvicorn`).*

### 2.3. Iniciar o Servidor FastAPI

Dentro da pasta `backend/`:

```bash
./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

O backend estará disponível em:
- **API Base URL**: http://localhost:8000
- **Documentação Interativa (Swagger UI)**: http://localhost:8000/docs
- **Redoc**: http://localhost:8000/redoc

---

## 3. Configurando e Rodando o Frontend (Next.js)

Em um novo terminal, acesse a pasta `frontend/`:

### 3.1. Configurar Variáveis de Ambiente

```bash
cd frontend
cp .env.example .env.local
```

Por padrão, `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` conecta o frontend ao FastAPI local.

### 3.2. Instalar Dependências e Rodar em Modo de Desenvolvimento

```bash
npm ci
npm run dev
```

O frontend estará disponível em:
- **Aplicação Web**: http://localhost:3000

Na interface:
1. Envie um arquivo PDF (ex.: `Proposta_Projeto_CogniFlow_AI.pdf` ou `fotossintese-texto-selecionavel.pdf`).
2. Informe o tema ou dúvida de estudo e escolha a **Abrangência do mapa** (**Essencial — 5 trechos**, **Detalhada — 10 trechos**, **Ampla — 15 trechos** ou **Completa — 20 trechos**).
3. Explore os conceitos no **Mapa** visual (com código de cores para *Tema central*, *Eixo temático*, *Conceito* e *Exemplo prático*) ou selecione **Lista** para leitura linear estruturada. A alternância preserva posições, zoom e seleção do mapa.

Detalhes da arquitetura de componentes e fluxo de dados estão em [docs/arquitetura-frontend.md](docs/arquitetura-frontend.md).

Para gerar o build de produção do frontend:

```bash
npm run build
npm run start
```

---

## 4. Testando os Endpoints da API (Exemplos via `curl`)

Com o banco de dados e o backend rodando em `http://localhost:8000`:

### 4.1. Health Check (`GET /api/health`)

```bash
curl -X GET http://localhost:8000/api/health
```

### 4.2. Ingestão e Vetorização de um PDF (`POST /api/documents/ingest`)

```bash
curl -X POST http://localhost:8000/api/documents/ingest \
  -F "file=@Proposta_Projeto_CogniFlow_AI.pdf;type=application/pdf"
```

### 4.3. Consulta de Chunks Armazenados de um Documento (`GET /api/documents/{document_name}/chunks`)

```bash
curl -X GET http://localhost:8000/api/documents/Proposta_Projeto_CogniFlow_AI.pdf/chunks
```

### 4.4. Geração de Mapa Mental via RAG (`POST /api/generate-map`)

O parâmetro `top_k` aceita valores de `1` a `20` (na interface, os presets correspondem a `5`, `10`, `15` e `20`):

```bash
curl -X POST http://localhost:8000/api/generate-map \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Arquitetura Técnica PostgreSQL pgvector FastAPI",
    "document_name": "Proposta_Projeto_CogniFlow_AI.pdf",
    "top_k": 10
  }'
```

---

## 5. Executando os Testes e a Demonstração do Pitch

### 5.1. Rodar a Suíte Completa de Testes do Backend (PyTest + Testcontainers)

Na raiz do projeto (com o serviço do Docker ativo, pois o **Testcontainers** sobe automaticamente uma instância isolada do `pgvector/pgvector:pg16`):

```bash
./backend/.venv/bin/pytest -c backend/pyproject.toml backend/tests -v
```

### 5.2. Rodar o Script de Demonstração ao Vivo (Pitch)

Para executar a conversão fim-a-fim do PDF da proposta com medição de **Recall** e **Latência**:

```bash
PYTHONPATH=backend ./backend/.venv/bin/python backend/scripts/demo_pitch.py
```

### 5.3. Verificar o Frontend (Lint, Tipos, Testes Unitários e E2E)

Em outro terminal, a partir da pasta `frontend/`:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm test
npm run build
```

#### Testes End-to-End e Auditoria de Acessibilidade (Playwright + axe-core)

- **Execução padrão (com API simulada):** Valida interações do grafo, navegação por teclado, alternância Mapa/Lista e auditorias automáticas de acessibilidade (`axe-core`) sem exigir o backend ativo:
  ```bash
  npm run test:e2e
  ```

- **Execução integrada fim-a-fim (com FastAPI e `pgvector` reais):** Com o banco e o backend rodando em `http://127.0.0.1:8000`, habilite a variável `COGNIFLOW_INTEGRATION_URL` para executar também o fluxo real de upload de PDF, geração de mapa e leitura textual (`e2e/real-study-flow.spec.ts`):
  ```bash
  COGNIFLOW_INTEGRATION_URL=http://127.0.0.1:8000 npm run test:e2e
  ```
