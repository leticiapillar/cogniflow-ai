import type { AskResponse } from "./types";

export function createAnswer(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    found_in_material: true,
    answer: "A clorofila absorve a luz do sol.",
    key_points: ["A clorofila é um pigmento verde.", "Ela fica nos cloroplastos."],
    example: "A folha é verde por causa da clorofila.",
    terms: [{ term: "Pigmento", definition: "Substância que dá cor." }],
    citations: [{ chunk_index: 4, page_start: 2, page_end: 2, section_title: "Cloroplastos", excerpt: "Cloroplastos contêm clorofila." }],
    related_concepts: [],
    ...overrides,
  };
}

export function createNotFoundAnswer(): AskResponse {
  return createAnswer({
    found_in_material: false,
    answer: "Não encontrei isso no material da aula.",
    key_points: [],
    example: null,
    terms: [],
    citations: [],
    related_concepts: [{ node_id: "chlorophyll", label: "Clorofila" }],
  });
}
