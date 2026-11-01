import { randomUUID } from "node:crypto";
import { assertLocalApi, readProposalPdf, removeTestDocument } from "@/test-utils/real-api";
import { expect, it, vi } from "vitest";
import { ingestDocument } from "@/features/documents/services/ingest-document";
import { generateMindMap } from "./generate-mind-map";
import { adaptMindMap } from "../utils/graph-adapter";
import { layoutGraph } from "../utils/layout-graph";

it.skipIf(!process.env.COGNIFLOW_INTEGRATION_URL)("generates grounded concepts from a real ingested PDF and reports missing context", async () => {
  assertLocalApi(process.env.COGNIFLOW_INTEGRATION_URL!);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", process.env.COGNIFLOW_INTEGRATION_URL);
  const bytes = await readProposalPdf();
  const name = `cogniflow-stage3-${randomUUID()}.pdf`;

  try {
    const document = await ingestDocument(new File([new Uint8Array(bytes)], name, { type: "application/pdf" }));
    const map = await generateMindMap({ query: "Arquitetura técnica CogniFlow AI FastAPI pgvector RAG", document_name: document.document_name });

    expect(map.nodes.length).toBeGreaterThan(1);
    expect(map.edges.length).toBeGreaterThan(0);
    expect(map.source_chunks_used).toBeGreaterThan(0);
    expect(map.generation_latency_ms).toBeGreaterThanOrEqual(0);

    const graph = layoutGraph(adaptMindMap(map));

    expect(graph.nodes.map((node) => node.id)).toEqual(map.nodes.map((node) => node.id));
    expect(graph.edges.map(({ id, source, target, label }) => ({ id, source, target, label })))
      .toEqual(map.edges.map(({ id, source, target, label }) => ({ id, source, target, label })));
    expect(graph.nodes.every((node) => Number.isFinite(node.position.x) && Number.isFinite(node.position.y))).toBe(true);

    const noContext = await generateMindMap({ query: "Arquitetura técnica", document_name: `missing-${name}` });

    expect(noContext.source_chunks_used).toBe(0);
  } finally {
    await removeTestDocument(name);
  }
}, 120_000);
