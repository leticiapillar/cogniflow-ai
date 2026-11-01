import type { Edge, Node } from "@xyflow/react";
import type { MindMapNodeData } from "./types";

export type ConceptNodeData = MindMapNodeData & { isRoot: boolean } & Record<string, unknown>;
export type ConceptFlowNode = Node<ConceptNodeData, "concept">;
export type ConceptFlowEdge = Edge;
export type MindMapGraph = { nodes: ConceptFlowNode[]; edges: ConceptFlowEdge[] };
