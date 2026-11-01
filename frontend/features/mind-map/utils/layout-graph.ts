import { graphlib, layout } from "@dagrejs/dagre";
import { CONCEPT_NODE_SIZE } from "../graph-config";
import type { MindMapGraph } from "../flow-types";

export function layoutGraph(graph: MindMapGraph): MindMapGraph {
  const dagreGraph = new graphlib.Graph({ multigraph: true });
  dagreGraph.setGraph({ rankdir: "TB", nodesep: 56, ranksep: 96, marginx: 24, marginy: 24 });
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  for (const node of graph.nodes) {
    dagreGraph.setNode(node.id, {
      width: node.width ?? CONCEPT_NODE_SIZE.width,
      height: node.height ?? CONCEPT_NODE_SIZE.height,
    });
  }

  for (const edge of graph.edges) {
    dagreGraph.setEdge(edge.source, edge.target, {}, edge.id);
  }

  layout(dagreGraph);

  return {
    nodes: graph.nodes.map((node) => {
      const position = dagreGraph.node(node.id);
      return {
        ...node,
        data: { ...node.data },
        position: {
          x: position.x - (node.width ?? CONCEPT_NODE_SIZE.width) / 2,
          y: position.y - (node.height ?? CONCEPT_NODE_SIZE.height) / 2,
        },
      };
    }),
    edges: graph.edges.map((edge) => ({ ...edge })),
  };
}
