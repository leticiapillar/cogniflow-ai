import type { GenerateMapResponse, ValidatedGenerateMapRequest } from "./types";

export const sampleRequest: ValidatedGenerateMapRequest = {
  query: "Como funciona a fotossíntese?",
  document_name: "biologia.pdf",
  top_k: 5,
};

export function createMapResponse(): GenerateMapResponse {
  return {
    topic: "Fotossíntese",
    nodes: [
      { id: "root", type: "input", data: { label: "Fotossíntese", summary: "Conversão de energia luminosa." }, position: { x: 0, y: 0 } },
      { id: "chlorophyll", type: "default", data: { label: "Clorofila", summary: "Pigmento que absorve luz." }, position: { x: 0, y: 140 } },
    ],
    edges: [{ id: "root-chlorophyll", source: "root", target: "chlorophyll", label: "utiliza", animated: false }],
    source_chunks_used: 2,
    generation_latency_ms: 15.5,
  };
}
