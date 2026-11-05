import type { z } from "zod";
import type { ApiError } from "@/services/http-client";
import type {
  mindMapEdgeSchema,
  mindMapNodeDataSchema,
  mindMapNodeSchema,
  mindMapSchema,
  mindMapStatusSchema,
  nodePositionSchema,
} from "./schemas";

export type MindMap = z.infer<typeof mindMapSchema>;
export type NodePosition = z.infer<typeof nodePositionSchema>;
export type MindMapNodeData = z.infer<typeof mindMapNodeDataSchema>;
export type MindMapNode = z.infer<typeof mindMapNodeSchema>;
export type MindMapEdge = z.infer<typeof mindMapEdgeSchema>;
export type MindMapStatusResponse = z.infer<typeof mindMapStatusSchema>;
export type FailedSection = MindMapStatusResponse["failed_sections"][number];

export type MindMapState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "generating"; response: MindMapStatusResponse }
  | { status: "ready"; response: MindMapStatusResponse; map: MindMap }
  | { status: "failed"; response: MindMapStatusResponse }
  | { status: "missing" }
  | { status: "error"; error: ApiError };
