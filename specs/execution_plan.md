# Plano de Execução: CogniFlow AI

## Sprint 1: Setup da Arquitetura e Infraestrutura Base
- [x] Inicializar o backend em Python utilizando o framework assíncrono FastAPI (configurar arquivos, logs e variáveis em inglês).
- [x] Estruturar o projeto seguindo Clean Architecture (`routers`, `use_cases` e `repositories`).
- [x] Provisionar o banco de dados vetorial PostgreSQL com a extensão `pgvector` via Docker Compose.
- [x] Configurar o ambiente de testes integrados no backend utilizando PyTest e Testcontainers (escrever funções de teste em inglês).
- [x] Inicializar o repositório frontend utilizando Next.js.
- [x] Definir os contratos da API REST (schemas Pydantic nomeados em inglês) para a comunicação entre frontend e backend.

## Sprint 2: Motor de Ingestão e Vetorização (RAG - Phase 1)
- [x] Integrar biblioteca de processamento (ex: PyPDF2 ou LlamaParse) para extração de texto dos PDFs (nomear funções de `parsing` em inglês).
- [x] Implementar algoritmos de *chunking* semântico para dividir o texto (tamanho fixo com *overlap* ou por cabeçalhos).
- [x] Configurar orquestrador (LangChain ou LlamaIndex) para gerenciar o pipeline de dados.
- [x] Integrar o modelo de *embeddings* e persistir os vetores no `pgvector`.
- [x] Adicionar camada de sanitização e validação de input no FastAPI para prevenir injeção de *prompt*.

## Sprint 3: Orquestração LLM e Geração em JSON Mode (RAG - Phase 2)
- [x] Desenvolver o algoritmo de busca por similaridade (RAG) para recuperar blocos de texto relevantes.
- [x] Configurar a chamada para a API do LLM.
- [x] Refinar o *System Prompt* (escrito integralmente em inglês) instruindo o modelo a responder estritamente em formato JSON (`nodes` e `edges`).
- [x] Implementar validação do contrato de saída no backend utilizando modelos do Pydantic para prevenir alucinação estrutural.
- [x] Construir mecanismo de abstração para facilitar a futura troca do modelo por um LLM open-source local via Ollama.

## Sprint 4: Interface Visual Interativa (Next.js + React Flow)
- [x] Configurar a biblioteca React Flow no projeto Next.js para o ambiente de mapas mentais.
- [x] Consumir o endpoint do FastAPI (`/api/generate-map`) e tratar as respostas no frontend.
- [x] Integrar motor de auto-layout (como Dagre.js) para calcular o espaçamento (X e Y) dos nós de forma automática.
- [x] Desenvolver componentes de interface focados em acessibilidade para minimizar a sobrecarga cognitiva.
- [x] Tratar cenários de carregamento (*loading states*) e mensagens de erro amigáveis na UI.

## Sprint 5: Homologação, Testes e Preparação para o Pitch
- [x] Escrever testes no PyTest iterando sobre os 20 exemplos reais de materiais acadêmicos.
- [x] Implementar métrica de Cobertura (*Recall*), cruzando entidades do PDF com os nós do JSON gerado.
- [x] Medir a Taxa de Sucesso de Renderização e monitorar a latência fim-a-fim da aplicação.
- [x] Garantir o isolamento de variáveis de ambiente para evitar vazamento de chaves institucionais.
- [x] Roteirizar e testar ao vivo a demonstração do protótipo convertendo um PDF.
