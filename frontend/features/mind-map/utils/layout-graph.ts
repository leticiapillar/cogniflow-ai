import { graphlib, layout } from "@dagrejs/dagre";
import { CONCEPT_NODE_SIZE } from "../graph-config";
import type { ConceptFlowNode, MindMapGraph } from "../flow-types";

const NODE_GAP = 56;
const RANK_GAP = 96;
const MARGIN = 24;

const widthOf = (node: ConceptFlowNode) => node.width ?? CONCEPT_NODE_SIZE.width;
const heightOf = (node: ConceptFlowNode) => node.height ?? CONCEPT_NODE_SIZE.height;

/** Children of each node when the graph is a forest (one parent per node, no cycles). */
function forestChildren(graph: MindMapGraph): Map<string, ConceptFlowNode[]> | null {
  const nodes = new Map(graph.nodes.map((node) => [node.id, node]));
  const children = new Map<string, ConceptFlowNode[]>();
  const parentOf = new Map<string, string>();

  for (const edge of graph.edges) {
    const child = nodes.get(edge.target);
    if (!child || !nodes.has(edge.source) || parentOf.has(edge.target)) return null;
    parentOf.set(edge.target, edge.source);
    children.set(edge.source, [...(children.get(edge.source) ?? []), child]);
  }

  for (const id of nodes.keys()) {
    const seen = new Set<string>();
    for (let current: string | undefined = id; current; current = parentOf.get(current)) {
      if (seen.has(current)) return null; // cycle
      seen.add(current);
    }
  }

  // Study axes follow their numbered order; other siblings keep the relation order.
  for (const list of children.values()) {
    list.sort((a, b) => (a.data.order ?? Number.MAX_SAFE_INTEGER) - (b.data.order ?? Number.MAX_SAFE_INTEGER));
  }
  return children;
}

/** Tidy top-down tree: siblings left to right in a fixed, predictable order. */
function layoutForest(graph: MindMapGraph, children: Map<string, ConceptFlowNode[]>): Map<string, { x: number; y: number }> {
  const hasParent = new Set(graph.edges.map((edge) => edge.target));
  const subtreeWidth = new Map<string, number>();

  const measure = (node: ConceptFlowNode): number => {
    const kids = children.get(node.id) ?? [];
    const kidsWidth = kids.reduce((sum, kid) => sum + measure(kid), 0) + NODE_GAP * Math.max(0, kids.length - 1);
    const width = Math.max(widthOf(node), kidsWidth);
    subtreeWidth.set(node.id, width);
    return width;
  };

  const positions = new Map<string, { x: number; y: number }>();
  const rankHeight = Math.max(CONCEPT_NODE_SIZE.height, ...graph.nodes.map(heightOf));

  const place = (node: ConceptFlowNode, left: number, depth: number) => {
    const width = subtreeWidth.get(node.id)!;
    positions.set(node.id, { x: left + (width - widthOf(node)) / 2, y: MARGIN + depth * (rankHeight + RANK_GAP) });

    const kids = children.get(node.id) ?? [];
    const kidsWidth = kids.reduce((sum, kid) => sum + subtreeWidth.get(kid.id)!, 0) + NODE_GAP * Math.max(0, kids.length - 1);
    let cursor = left + (width - kidsWidth) / 2;
    for (const kid of kids) {
      place(kid, cursor, depth + 1);
      cursor += subtreeWidth.get(kid.id)! + NODE_GAP;
    }
  };

  let left = MARGIN;
  for (const root of graph.nodes.filter((node) => !hasParent.has(node.id))) {
    const width = measure(root);
    place(root, left, 0);
    left += width + NODE_GAP;
  }
  return positions;
}

function layoutWithDagre(graph: MindMapGraph): Map<string, { x: number; y: number }> {
  const dagreGraph = new graphlib.Graph({ multigraph: true });
  dagreGraph.setGraph({ rankdir: "TB", nodesep: NODE_GAP, ranksep: RANK_GAP, marginx: MARGIN, marginy: MARGIN });
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  for (const node of graph.nodes) {
    dagreGraph.setNode(node.id, { width: widthOf(node), height: heightOf(node) });
  }
  for (const edge of graph.edges) {
    dagreGraph.setEdge(edge.source, edge.target, {}, edge.id);
  }

  layout(dagreGraph);

  return new Map(graph.nodes.map((node) => {
    const center = dagreGraph.node(node.id);
    return [node.id, { x: center.x - widthOf(node) / 2, y: center.y - heightOf(node) / 2 }];
  }));
}

export function layoutGraph(graph: MindMapGraph): MindMapGraph {
  const children = forestChildren(graph);
  // A valid mind map is always a tree; Dagre only handles unexpected shapes.
  const positions = children ? layoutForest(graph, children) : layoutWithDagre(graph);

  return {
    nodes: graph.nodes.map((node) => ({
      ...node,
      data: { ...node.data },
      position: { ...positions.get(node.id)! },
    })),
    edges: graph.edges.map((edge) => ({ ...edge })),
  };
}
