import { z } from "zod";

export const COVERAGE_OPTIONS = [
  { value: 5, label: "Essencial (5 trechos)", description: "Foco nos conceitos mais diretos para respostas rápidas." },
  { value: 10, label: "Detalhada (10 trechos)", description: "Equilíbrio entre conceitos principais, pilares e exemplos." },
  { value: 15, label: "Ampla (15 trechos)", description: "Cobertura aprofundada conectando múltiplas seções do PDF." },
  { value: 20, label: "Completa (20 trechos)", description: "Visão global de todo o material (ideal para resumos de capítulos)." },
] as const;

export const generateMapRequestSchema = z.object({
  query: z.string({ error: "Informe o tema que você quer estudar." })
    .trim()
    .min(3, "Escreva uma consulta com pelo menos 3 caracteres.")
    .max(2000, "A consulta deve ter no máximo 2.000 caracteres."),
  document_name: z.string().trim().min(1, "Selecione um documento válido.").nullish(),
  top_k: z.number({ error: "A quantidade de trechos deve ser um número inteiro." })
    .int("A quantidade de trechos deve ser inteira.")
    .min(1, "A quantidade de trechos deve ser entre 1 e 20.")
    .max(20, "A quantidade de trechos deve ser entre 1 e 20.")
    .default(5),
});

export const nodePositionSchema = z.object({ x: z.number().finite(), y: z.number().finite() });

export const mindMapNodeDataSchema = z.object({
  label: z.string().trim().min(1).max(200),
  summary: z.string().max(1000).nullish(),
  category: z.string().nullish(),
});

export const mindMapNodeSchema = z.object({
  id: z.string().min(1),
  type: z.string(),
  data: mindMapNodeDataSchema,
  position: nodePositionSchema,
});

export const mindMapEdgeSchema = z.object({
  id: z.string().min(1),
  source: z.string().min(1),
  target: z.string().min(1),
  label: z.string().max(120).nullish(),
  animated: z.boolean(),
});

export const generateMapResponseSchema = z.object({
  topic: z.string().trim().min(1),
  nodes: z.array(mindMapNodeSchema).min(1),
  edges: z.array(mindMapEdgeSchema),
  source_chunks_used: z.number().int().nonnegative(),
  generation_latency_ms: z.number().finite().nonnegative(),
}).superRefine((map, context) => {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();

  map.nodes.forEach((node, index) => {
    if (nodeIds.has(node.id)) {
      context.addIssue({ code: "custom", path: ["nodes", index, "id"], message: "Identificador de conceito duplicado." });
    }
    nodeIds.add(node.id);
  });

  map.edges.forEach((edge, index) => {
    if (edgeIds.has(edge.id)) {
      context.addIssue({ code: "custom", path: ["edges", index, "id"], message: "Identificador de relação duplicado." });
    }
    edgeIds.add(edge.id);
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target) || edge.source === edge.target) {
      context.addIssue({ code: "custom", path: ["edges", index], message: "A relação contém uma referência inválida." });
    }
  });
});
