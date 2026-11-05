import { z } from "zod";

export const nodeCategorySchema = z.enum(["root", "topic", "concept", "example"]);

export const relationTypeSchema = z.enum([
  "has_part",
  "is_a",
  "causes",
  "depends_on",
  "precedes",
  "contrasts",
  "exemplified_by",
]);

export const nodePositionSchema = z.object({ x: z.number().finite(), y: z.number().finite() });

export const mindMapNodeDataSchema = z.object({
  label: z.string().trim().min(1).max(200),
  summary: z.string().max(1000).nullish(),
  category: nodeCategorySchema,
  order: z.number().int().positive().nullish(),
  acronyms: z.record(z.string(), z.string()).default({}),
  source_chunks: z.array(z.number().int().nonnegative()).default([]),
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
  relation: relationTypeSchema,
  label: z.string().max(120),
  animated: z.boolean(),
});

export const mindMapSchema = z.object({
  topic: z.string().trim().min(1),
  nodes: z.array(mindMapNodeSchema).min(1),
  edges: z.array(mindMapEdgeSchema),
}).superRefine((map, context) => {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();

  map.nodes.forEach((node, index) => {
    if (nodeIds.has(node.id)) {
      context.addIssue({ code: "custom", path: ["nodes", index, "id"], message: "Identificador de conceito duplicado." });
    }
    nodeIds.add(node.id);
  });

  if (map.nodes.filter((node) => node.data.category === "root").length !== 1) {
    context.addIssue({ code: "custom", path: ["nodes"], message: "O mapa deve ter exatamente um tema central." });
  }

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

export const mindMapStatusValueSchema = z.enum(["pending", "processing", "ready", "partial", "failed"]);

export const mindMapStatusSchema = z.object({
  document_id: z.uuid(),
  document_name: z.string().min(1),
  status: mindMapStatusValueSchema,
  progress: z.object({
    phase: z.enum(["pending", "mapping", "consolidating", "organizing", "done"]),
    done: z.number().int().nonnegative(),
    total: z.number().int().nonnegative(),
    current_section: z.string().nullish(),
    message: z.string().min(1),
  }),
  failed_sections: z.array(z.object({
    section_index: z.number().int().nonnegative(),
    section_title: z.string().nullish(),
    reason: z.string(),
  })),
  mind_map: mindMapSchema.nullish(),
  llm_model: z.string(),
  error: z.string().nullish(),
  updated_at: z.string(),
}).superRefine((status, context) => {
  const hasMap = Boolean(status.mind_map);
  if ((status.status === "ready" || status.status === "partial") && !hasMap) {
    context.addIssue({ code: "custom", path: ["mind_map"], message: "O mapa pronto não foi enviado." });
  }
});
