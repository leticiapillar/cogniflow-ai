import type { MindMap, MindMapStatusResponse } from "./types";

export const DOCUMENT_ID = "8b6f2a51-3c0e-4f43-9a7d-5d2c1f0e9a11";

export function createMapResponse(): MindMap {
  const node = (id: string, label: string, category: "root" | "topic" | "concept" | "example", extra = {}) => ({
    id,
    type: category === "root" ? "input" : "default",
    data: { label, summary: null, category, acronyms: {}, source_chunks: category === "root" ? [] : [1], ...extra },
    position: { x: 0, y: 0 },
  });

  return {
    topic: "Fotossíntese",
    nodes: [
      node("root", "Fotossíntese", "root", { summary: "Conversão de energia luminosa.", source_chunks: [1, 2] }),
      node("topic-1", "Estruturas da planta", "topic", { order: 1, summary: "Partes da planta que participam." }),
      node("chlorophyll", "Clorofila", "concept", { summary: "Pigmento que absorve luz." }),
      node("leaf", "Folha verde", "example", { summary: "A folha é verde por causa da clorofila." }),
      node("topic-2", "Etapas do processo", "topic", { order: 2, summary: "As fases da fotossíntese.", source_chunks: [2] }),
      node("light-phase", "Fase clara", "concept", {
        summary: "Usa a luz para produzir ATP.", acronyms: { ATP: "Adenosina trifosfato" }, source_chunks: [2],
      }),
    ],
    edges: [
      { id: "root-topic-1", source: "root", target: "topic-1", relation: "has_part", label: "inclui", animated: false },
      { id: "topic-1-chlorophyll", source: "topic-1", target: "chlorophyll", relation: "has_part", label: "inclui", animated: false },
      { id: "chlorophyll-leaf", source: "chlorophyll", target: "leaf", relation: "exemplified_by", label: "exemplificado por", animated: false },
      { id: "root-topic-2", source: "root", target: "topic-2", relation: "has_part", label: "inclui", animated: false },
      { id: "topic-2-light-phase", source: "topic-2", target: "light-phase", relation: "depends_on", label: "depende de", animated: false },
    ],
  };
}

export function createStatusResponse(overrides: Partial<MindMapStatusResponse> = {}): MindMapStatusResponse {
  return {
    document_id: DOCUMENT_ID,
    document_name: "biologia.pdf",
    status: "ready",
    progress: { phase: "done", done: 2, total: 2, current_section: null, message: "Mapa pronto." },
    failed_sections: [],
    mind_map: createMapResponse(),
    llm_model: "llama3.2:3b",
    error: null,
    updated_at: "2026-11-05T12:00:00Z",
    ...overrides,
  };
}

export function createProcessingStatus(done = 1, total = 3, section = "Cloroplastos"): MindMapStatusResponse {
  return createStatusResponse({
    status: "processing",
    progress: { phase: "mapping", done, total, current_section: section, message: `Lendo a seção ${done + 1} de ${total}: ${section}.` },
    mind_map: null,
  });
}
