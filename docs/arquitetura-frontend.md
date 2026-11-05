# Estrutura do frontend — CogniFlow AI

O frontend está localizado em `frontend/` e utiliza Next.js, React, TypeScript, Tailwind CSS e React Flow. O código é organizado por funcionalidade, com elementos compartilhados fora das features.

## Estrutura de diretórios

```text
frontend/
├── app/
│   ├── favicon.ico
│   ├── icon.svg
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── study-workspace.tsx
│   └── ui/
│       └── status-message.tsx
├── features/
│   ├── documents/
│   │   ├── components/document-upload.tsx
│   │   ├── hooks/use-ingest-document.ts
│   │   ├── services/ingest-document.ts
│   │   ├── schemas.ts
│   │   └── types.ts
│   ├── mind-map/
│   │   ├── components/
│   │   │   ├── concept-details.tsx
│   │   │   ├── mind-map-error-boundary.tsx
│   │   │   ├── mind-map-node.tsx
│   │   │   ├── mind-map-outline.tsx
│   │   │   ├── mind-map-panel.tsx
│   │   │   ├── mind-map-progress.tsx
│   │   │   ├── mind-map-toolbar.tsx
│   │   │   └── mind-map-viewer.tsx
│   │   ├── hooks/use-mind-map.ts
│   │   ├── services/mind-map-api.ts
│   │   ├── utils/
│   │   │   ├── graph-adapter.ts
│   │   │   ├── layout-graph.ts
│   │   │   └── tree.ts
│   │   ├── expansion.tsx
│   │   ├── flow-types.ts
│   │   ├── graph-config.ts
│   │   ├── schemas.ts
│   │   ├── test-fixtures.ts
│   │   └── types.ts
│   ├── service-status/
│   │   ├── components/service-status.tsx
│   │   ├── hooks/use-service-health.ts
│   │   └── services/get-service-health.ts
│   └── tutor/
│       ├── components/
│       │   ├── tutor-answer.tsx
│       │   └── tutor-panel.tsx
│       ├── hooks/use-tutor.ts
│       ├── services/ask-tutor.ts
│       ├── schemas.ts
│       ├── test-fixtures.ts
│       └── types.ts
├── services/
│   └── http-client.ts
├── e2e/
│   ├── helpers/study-flow.ts
│   ├── accessibility.spec.ts
│   ├── mind-map.spec.ts
│   └── real-study-flow.spec.ts
├── test-utils/
│   └── real-api.ts
├── .env.example
├── eslint.config.mjs
├── next.config.ts
├── package.json
├── playwright.config.ts
├── tsconfig.json
└── vitest.config.mts
```

Os testes unitários e de componentes usam os sufixos `.test.ts` e `.test.tsx` e ficam ao lado dos arquivos testados.

## Aplicação

### `app/`

- `layout.tsx`: layout raiz, idioma e metadados da aplicação.
- `page.tsx`: página inicial e composição do workspace.
- `globals.css`: tokens visuais, estilos globais e personalização do React Flow.
- `icon.svg` e `favicon.ico`: ícones da aplicação.

### `components/`

Contém componentes utilizados na composição geral da página.

- `study-workspace.tsx`: conecta as features: verificação do serviço de IA → envio do PDF → acompanhamento do mapa → tutor, incluindo a ação "Tirar dúvida sobre este conceito".
- `ui/status-message.tsx`: região compartilhada para mensagens de estado.

## Features

### `features/documents/`

Reúne o fluxo de seleção, validação e envio de PDFs.

- `components/`: interface de upload.
- `hooks/`: estado da ingestão, cancelamento e descarte de respostas antigas.
- `services/`: chamada ao endpoint de ingestão.
- `schemas.ts`: schemas Zod do arquivo e da resposta.
- `types.ts`: tipos da feature.

### `features/mind-map/`

Acompanha a geração do mapa do material inteiro (feita em segundo plano pelo backend) e o apresenta com exibição progressiva.

- `hooks/use-mind-map.ts`: consulta `GET /api/documents/{id}/mind-map` a cada 2 segundos enquanto o mapa é gerado; expõe gerar novamente e tentar de novo uma seção.
- `services/mind-map-api.ts`: chamadas de status, regeneração e nova tentativa de seção, com mensagens literais para 404 e 409.
- `components/mind-map-panel.tsx`: estados do mapa (gerando, pronto, parcial, falhou, sem mapa, erro), alternância Mapa/Lista e "Abrir/Fechar todos os eixos".
- `components/mind-map-progress.tsx`: progresso em três etapas fixas e barra de seções lidas.
- `expansion.tsx`: estado dos eixos abertos, compartilhado entre o mapa e a lista (preservado ao alternar).
- `components/mind-map-viewer.tsx` e `mind-map-node.tsx`: canvas React Flow que mostra o tema e os eixos numerados; cada eixo tem o botão Abrir/Fechar.
- `components/mind-map-outline.tsx`: a mesma leitura progressiva em lista, para teclado e leitor de tela.
- `components/concept-details.tsx`: resumo, siglas, relações e as ações "Abrir eixo" e "Tirar dúvida sobre este conceito".
- `utils/tree.ts`: eixos em ordem de estudo, filhos de cada nó e nós visíveis.
- `utils/layout-graph.ts`: layout em árvore com os eixos da esquerda para a direita na ordem numerada (Dagre apenas para grafos que não são árvore).
- `utils/graph-adapter.ts`: conversão da resposta da API para nós e conexões do React Flow.

### `features/service-status/`

Consulta `GET /api/health` ao carregar a página. Enquanto o serviço de IA não estiver pronto, mostra o aviso com "Verificar novamente" e mantém o envio de PDF desabilitado.

### `features/tutor/`

Tira-dúvidas com RAG sobre o material.

- `hooks/use-tutor.ts`: sessão de perguntas do documento atual (reiniciada ao trocar de material), histórico com as últimas 4 trocas e o conceito do mapa em foco.
- `services/ask-tutor.ts`: `POST /api/documents/{id}/ask`, com mensagens literais para 404, 409, 422 e 503.
- `components/tutor-panel.tsx`: conversa, campo da dúvida com limite de 1.000 caracteres e foco movido para cada resposta nova.
- `components/tutor-answer.tsx`: resposta sempre na mesma ordem (resposta → pontos principais → exemplo → termos → onde está no material, com página e seção).

## Código compartilhado

### `services/http-client.ts`

Cliente HTTP utilizado pelas features. Centraliza a URL do backend, requisições com `fetch`, timeout, cancelamento, leitura das respostas e classificação dos erros.

### `test-utils/`

Funções usadas pelos testes de integração para acessar o PDF do projeto, validar a URL local da API e limpar documentos criados durante os testes.

## Testes

- Testes próximos ao código: Vitest e Testing Library.
- `e2e/accessibility.spec.ts`: axe-core, teclado (incluindo o tutor), serviço de IA indisponível e estados de erro.
- `e2e/mind-map.spec.ts`: exibição progressiva dos eixos, progresso da geração, mapa parcial, zoom e layout.
- `e2e/real-study-flow.spec.ts`: fluxo completo com PDF, backend e Ollama reais (PDF → mapa → dúvida).
- `e2e/helpers/study-flow.ts`: preparação e simulação da API nos testes de navegador.

As configurações estão em `vitest.config.mts` e `playwright.config.ts`.

## Fluxo entre os módulos

```text
app/page.tsx
└── components/study-workspace.tsx
    ├── features/service-status  → GET /api/health (habilita o envio)
    ├── features/documents       → POST /api/documents/ingest
    ├── features/mind-map        → GET /api/documents/{id}/mind-map (polling)
    │   └── mapa → adapter → layout em árvore → React Flow ou lista textual
    └── features/tutor           → POST /api/documents/{id}/ask
```

O workspace recebe o documento preparado pela feature `documents`, acompanha a geração do mapa pela feature `mind-map` e habilita o `tutor` quando o mapa fica pronto. As features acessam o backend pelos seus próprios serviços, usando o cliente HTTP compartilhado.
