import type { z } from "zod";
import type { ApiError } from "@/services/http-client";
import type {
  generateMapRequestSchema,
  generateMapResponseSchema,
  mindMapEdgeSchema,
  mindMapNodeDataSchema,
  mindMapNodeSchema,
  nodePositionSchema,
} from "./schemas";

export type GenerateMapRequest = z.input<typeof generateMapRequestSchema>;
export type ValidatedGenerateMapRequest = z.output<typeof generateMapRequestSchema>;
export type GenerateMapResponse = z.infer<typeof generateMapResponseSchema>;
export type NodePosition = z.infer<typeof nodePositionSchema>;
export type MindMapNodeData = z.infer<typeof mindMapNodeDataSchema>;
export type MindMapNode = z.infer<typeof mindMapNodeSchema>;
export type MindMapEdge = z.infer<typeof mindMapEdgeSchema>;

export type GenerationState =
  | { status: "idle" }
  | { status: "generating"; request: ValidatedGenerateMapRequest }
  | { status: "success"; request: ValidatedGenerateMapRequest; map: GenerateMapResponse }
  | { status: "error"; error: ApiError };
