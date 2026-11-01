# CogniFlow AI

**Traduzindo Texto Denso em Aprendizado Visual**

O **CogniFlow AI** é uma plataforma educacional assistiva que utiliza **RAG (Retrieval-Augmented Generation)** e **IA Generativa** para converter materiais acadêmicos densos (PDFs, apostilas e transcrições) em mapas mentais visuais estruturados, reduzindo a sobrecarga cognitiva para estudantes surdos e neurodivergentes (TDAH/TEA).

![Interface do CogniFlow AI](docs/cogniflow-interface.png)

---

## Arquitetura do Projeto

```text
cogniflow-ai/
├── docker-compose.yml          # PostgreSQL 16 + extensão pgvector
├── execution_plan.md           # Plano de execução dividido em 5 Sprints
├── docs/                       # Arquitetura, execução e validação do frontend
├── Proposta_Projeto_CogniFlow_AI.pdf
├── backend/                    # API Orquestradora (Python + FastAPI + Clean Architecture)
│   ├── app/
│   │   ├── core/               # Configurações (Pydantic Settings), logs e conexão assíncrona DB
│   │   ├── repositories/       # Persistência e busca por similaridade vetorial (pgvector)
│   │   ├── routers/            # Endpoints REST (/api/health, /api/documents, /api/generate-map)
│   │   ├── schemas/            # Contratos estritos de entrada/saída (Pydantic)
│   │   ├── services/           # PDF parser, chunking, sanitização, embeddings, LLM e métricas
│   │   └── use_cases/          # Regras de negócio da aplicação
│   ├── scripts/
│   │   ├── init_db.sql         # Script de inicialização da extensão vector
│   │   └── demo_pitch.py       # Script de demonstração ao vivo para o Pitch
│   └── tests/                  # Suíte de testes automatizados (PyTest + Testcontainers)
└── frontend/                   # Next.js 16 + TypeScript + Tailwind + React Flow
    ├── app/                    # App Router, layout e estilos
    ├── components/             # Composição e apresentação compartilhada
    ├── features/               # documents e mind-map: componentes, hooks e serviços
    ├── services/               # Cliente HTTP compartilhado
    └── e2e/                    # Playwright: interação, acessibilidade e fluxo real
```

Consulte a [estrutura do frontend](docs/arquitetura-frontend.md) para conhecer a organização das páginas, componentes, features, serviços e testes.

---

## Pré-requisitos

- **Docker** e **Docker Compose** (para o banco PostgreSQL + `pgvector` e para os testes com Testcontainers)
- **Python 3.11+** e `pip`
- **Node.js 20.19+** na linha 20, **22.12+** na linha 22 ou **24+**, e `npm`

---

## 1. Subindo o Banco de Dados Vetorial (`PostgreSQL + pgvector`)

Na raiz do projeto, inicie o container do banco de dados:

```bash
docker compose up -d
```

Para verificar se o banco está saudável (`healthy`):

```bash
docker compose ps
```

---

## 2. Configurando e Rodando o Backend (FastAPI)

### 2.1. Configurar Variáveis de Ambiente

Entre no diretório `backend/` e crie o arquivo `.env` a partir do template `.env.example`:

```bash
cd backend
cp .env.example .env
```

> **Configuração de Modelos (Opcional):**
> - Por padrão, `EMBEDDING_PROVIDER="local"` e `LLM_PROVIDER="local"` permitem rodar toda a aplicação localmente sem necessidade de chave de API externa.
> - Para usar **Google Gemini**, altere `LLM_PROVIDER="gemini"`, `EMBEDDING_PROVIDER="gemini"` e preencha `GEMINI_API_KEY="sua_chave"`.
> - Para usar **Ollama** (modelos locais abertos como Llama/Qwen com total privacidade LGPD), altere `LLM_PROVIDER="ollama"` e `EMBEDDING_PROVIDER="ollama"`.

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

### 3.2. Instalar Dependências e Rodar em Modo de Desenvolvimento

```bash
npm ci
npm run dev
```

O frontend estará disponível em:
- **Aplicação Web**: http://localhost:3000

Na interface, envie um PDF, informe o tema de estudo e gere os conceitos. Use o mapa para explorar as conexões ou selecione **Lista** para ler conceitos, resumos e relações em texto. A alternância preserva posições, zoom e seleção do mapa. Configuração, testes e limites de acessibilidade estão no [README do frontend](frontend/README.md).

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

### 4.3. Geração de Mapa Mental via RAG (`POST /api/generate-map`)

```bash
curl -X POST http://localhost:8000/api/generate-map \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Arquitetura Técnica PostgreSQL pgvector FastAPI",
    "document_name": "Proposta_Projeto_CogniFlow_AI.pdf",
    "top_k": 5
  }'
```

---

## 5. Executando os Testes e a Demonstração do Pitch

### 5.1. Rodar a Suíte Completa de Testes (PyTest + Testcontainers)

Na raiz do projeto (com o serviço do Docker ativo, pois o **Testcontainers** sobe automaticamente uma instância isolada do `pgvector/pgvector:pg16`):

```bash
./backend/.venv/bin/pytest -c backend/pyproject.toml backend/tests -v
```

### 5.2. Rodar o Script de Demonstração ao Vivo (Pitch)

Para executar a conversão fim-a-fim do PDF da proposta com medição de **Recall** e **Latência**:

```bash
PYTHONPATH=backend ./backend/.venv/bin/python backend/scripts/demo_pitch.py
```

### 5.3. Verificar o Frontend

Em outro terminal, a partir da raiz:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm test
npm run build
```

Com Google Chrome instalado, execute `npm run test:e2e`. A execução padrão usa respostas HTTP simuladas e não exige o backend. O [README do frontend](frontend/README.md) documenta também os testes com FastAPI e pgvector reais e as auditorias de acessibilidade.

