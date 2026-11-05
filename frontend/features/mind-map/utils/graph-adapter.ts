import { MarkerType, Position } from "@xyflow/react";
import { CONCEPT_NODE_SIZE, getCategoryMeta } from "../graph-config";
import type { MindMapGraph } from "../flow-types";
import type { MindMap } from "../types";

export function adaptMindMap(map: MindMap): MindMapGraph {
  const labels = new Map(map.nodes.map((node) => [node.id, node.data.label]));

  return {
    nodes: map.nodes.map((node) => {
      const isRoot = node.type === "input" || node.data.category === "root";
      const meta = getCategoryMeta(node.data.category, isRoot, node.data.order);

      return {
        id: node.id,
        type: "concept",
        data: {
          ...node.data,
          acronyms: { ...node.data.acronyms },
          source_chunks: [...node.data.source_chunks],
          isRoot,
        },
        position: { ...node.position },
        width: CONCEPT_NODE_SIZE.width,
        height: CONCEPT_NODE_SIZE.height,
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        ariaLabel: `${meta.label}: ${node.data.label}. Selecione para ler os detalhes.`,
        deletable: false,
        connectable: false,
        domAttributes: { "aria-roledescription": "conceito" },
      };
    }),
    edges: map.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      ariaLabel: `Relação: ${labels.get(edge.source)} ${edge.label} ${labels.get(edge.target)}.`,
      domAttributes: { "aria-roledescription": "relação" },
      type: "smoothstep",
      animated: false,
      deletable: false,
      reconnectable: false,
      markerEnd: { type: MarkerType.ArrowClosed },
      labelStyle: { fontSize: 11 },
    })),
  };
}
