import type { MindMap, MindMapEdge, MindMapNode } from "../types";

export function childrenByParent(map: MindMap): Map<string, MindMapNode[]> {
  const nodes = new Map(map.nodes.map((node) => [node.id, node]));
  const children = new Map<string, MindMapNode[]>();

  for (const edge of map.edges) {
    const child = nodes.get(edge.target);
    if (child) children.set(edge.source, [...(children.get(edge.source) ?? []), child]);
  }
  return children;
}

export function parentEdgeOf(map: MindMap, nodeId: string): MindMapEdge | undefined {
  return map.edges.find((edge) => edge.target === nodeId);
}

export function rootOf(map: MindMap): MindMapNode {
  return map.nodes.find((node) => node.data.category === "root") ?? map.nodes[0];
}

/** Study axes in the suggested reading order. */
export function topicsInOrder(map: MindMap): MindMapNode[] {
  return map.nodes
    .filter((node) => node.data.category === "topic")
    .sort((a, b) => (a.data.order ?? Number.MAX_SAFE_INTEGER) - (b.data.order ?? Number.MAX_SAFE_INTEGER));
}

function descendants(nodeId: string, children: Map<string, MindMapNode[]>): string[] {
  return (children.get(nodeId) ?? []).flatMap((child) => [child.id, ...descendants(child.id, children)]);
}

/** Root and axes are always visible; an open axis shows its concepts and examples. */
export function visibleNodeIds(map: MindMap, expandedTopics: ReadonlySet<string>): Set<string> {
  const children = childrenByParent(map);
  const visible = new Set([rootOf(map).id]);

  for (const topic of topicsInOrder(map)) {
    visible.add(topic.id);
    if (expandedTopics.has(topic.id)) descendants(topic.id, children).forEach((id) => visible.add(id));
  }
  return visible;
}
