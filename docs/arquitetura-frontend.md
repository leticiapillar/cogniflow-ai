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
│   │   ├── components/
│   │   │   └── document-upload.tsx
│   │   ├── hooks/
│   │   │   └── use-ingest-document.ts
│   │   ├── services/
│   │   │   └── ingest-document.ts
│   │   ├── schemas.ts
│   │   └── types.ts
│   └── mind-map/
│       ├── components/
│       │   ├── concept-details.tsx
│       │   ├── mind-map-error-boundary.tsx
│       │   ├── mind-map-form.tsx
│       │   ├── mind-map-node.tsx
│       │   ├── mind-map-outline.tsx
│       │   ├── mind-map-result.tsx
│       │   ├── mind-map-toolbar.tsx
│       │   └── mind-map-viewer.tsx
│       ├── hooks/
│       │   └── use-generate-mind-map.ts
│       ├── services/
│       │   └── generate-mind-map.ts
│       ├── utils/
│       │   ├── graph-adapter.ts
│       │   └── layout-graph.ts
│       ├── flow-types.ts
│       ├── graph-config.ts
│       ├── schemas.ts
│       ├── test-fixtures.ts
│       └── types.ts
├── services/
│   └── http-client.ts
├── e2e/
│   ├── helpers/
│   │   └── study-flow.ts
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

- `study-workspace.tsx`: mantém o documento ativo e conecta as features de documentos e mapa mental.
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

Reúne a consulta, geração e visualização dos mapas mentais.

- `components/`: formulário, resultado, canvas, nós, controles, detalhes e leitura em lista.
- `hooks/`: estado da geração e controle das requisições.
- `services/`: chamada ao endpoint de geração.
- `utils/graph-adapter.ts`: conversão da resposta da API para nós e conexões do React Flow.
- `utils/layout-graph.ts`: posicionamento automático do grafo com Dagre.
- `schemas.ts`: schemas Zod da requisição e resposta.
- `types.ts`: tipos do contrato da API e dos estados da feature.
- `flow-types.ts`: tipos utilizados pelo React Flow.
- `graph-config.ts`: dimensões dos nós.
- `test-fixtures.ts`: dados reutilizados pelos testes.

## Código compartilhado

### `services/http-client.ts`

Cliente HTTP utilizado pelas features. Centraliza a URL do backend, requisições com `fetch`, timeout, cancelamento, leitura das respostas e classificação dos erros.

### `test-utils/`

Funções usadas pelos testes de integração para acessar o PDF do projeto, validar a URL local da API e limpar documentos criados durante os testes.

## Testes

- Testes próximos ao código: Vitest e Testing Library.
- `e2e/accessibility.spec.ts`: acessibilidade, teclado e estados de erro.
- `e2e/mind-map.spec.ts`: interação com nós, conexões, zoom e layout.
- `e2e/real-study-flow.spec.ts`: fluxo completo com PDF e backend reais.
- `e2e/helpers/study-flow.ts`: preparação e simulação da API nos testes de navegador.

As configurações estão em `vitest.config.mts` e `playwright.config.ts`.

## Fluxo entre os módulos

```text
app/page.tsx
└── components/study-workspace.tsx
    ├── features/documents
    │   └── hook → service → services/http-client.ts → FastAPI
    └── features/mind-map
        ├── hook → service → services/http-client.ts → FastAPI
        └── resposta → adapter → layout → React Flow ou lista textual
```

O workspace recebe o documento preparado pela feature `documents` e o utiliza na geração executada pela feature `mind-map`. As features acessam o backend pelos seus próprios serviços, usando o cliente HTTP compartilhado.

