export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  database_connected: boolean;
}

export interface NodePosition {
  x: number;
  y: number;
}

export interface MindMapNodeData {
  label: string;
  summary?: string | null;
  category?: string | null;
}

export interface MindMapNode {
  id: string;
  type: string;
  data: MindMapNodeData;
  position: NodePosition;
}

export interface MindMapEdge {
  id: string;
  source: string;
  target: string;
  label?: string | null;
  animated: boolean;
}

export interface GenerateMapRequest {
  query: string;
  document_name?: string | null;
  top_k?: number;
}

export interface GenerateMapResponse {
  topic: string;
  nodes: MindMapNode[];
  edges: MindMapEdge[];
  source_chunks_used: number;
}

