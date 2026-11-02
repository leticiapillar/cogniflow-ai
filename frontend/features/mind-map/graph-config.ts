export const CONCEPT_NODE_SIZE = { width: 248, height: 116 } as const;

export function getCategoryMeta(category?: string | null, isRoot?: boolean): {
  label: string;
  dotClass: string;
  nodeClass: string;
} {
  const normalized = category?.trim().toLowerCase();
  if (isRoot || normalized === "root") {
    return {
      label: "Tema central",
      dotClass: "bg-[#ff6b4a]",
      nodeClass: "concept-node-root",
    };
  }
  if (normalized === "topic") {
    return {
      label: "Eixo temático",
      dotClass: "bg-[#0284c7]",
      nodeClass: "concept-node-topic",
    };
  }
  if (normalized === "example") {
    return {
      label: "Exemplo prático",
      dotClass: "bg-[#059669]",
      nodeClass: "concept-node-example",
    };
  }
  return {
    label: "Conceito",
    dotClass: "bg-accent",
    nodeClass: "concept-node-concept",
  };
}
