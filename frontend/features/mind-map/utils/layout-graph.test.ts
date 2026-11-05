import { describe, expect, it } from "vitest";
import { createMapResponse } from "../test-fixtures";
import { adaptMindMap } from "./graph-adapter";
import { layoutGraph } from "./layout-graph";

/** Theme and one axis: the smallest tree, so each test controls every node. */
function smallMap() {
  const map = createMapResponse();
  map.nodes = map.nodes.slice(0, 2);
  map.edges = [map.edges[0]];
  return map;
}

describe("layoutGraph", () => {
  it("places children below parents with space between their bounding boxes", () => {
    const graph = layoutGraph(adaptMindMap(smallMap()));
    const [parent, child] = graph.nodes;

    expect(child.position.y).toBeGreaterThan(parent.position.y + parent.height!);
    expect(parent.position.x).toBeGreaterThanOrEqual(0);
    expect(parent.position.y).toBeGreaterThanOrEqual(0);
    expect(graph.nodes.every((node) => Number.isFinite(node.position.x) && Number.isFinite(node.position.y))).toBe(true);
  });

  it("keeps sibling nodes from overlapping and preserves all connections", () => {
    const map = smallMap();
    map.nodes.push({ ...map.nodes[1], id: "water", data: { ...map.nodes[1].data, label: "Água" } });
    map.edges.push({ ...map.edges[0], id: "root-water", target: "water" });
    const input = adaptMindMap(map);
    const graph = layoutGraph(input);
    const siblings = graph.nodes.slice(1).sort((a, b) => a.position.x - b.position.x);

    expect(siblings[1].position.x).toBeGreaterThan(siblings[0].position.x + siblings[0].width!);
    expect(graph.edges).toEqual(input.edges);
  });

  it("does not mutate the input and restores manual positions deterministically", () => {
    const input = adaptMindMap(smallMap());
    const before = structuredClone(input);
    const first = layoutGraph(input);

    expect(input).toEqual(before);

    const moved = { ...first, nodes: first.nodes.map((node) => ({ ...node, position: { x: 999, y: 999 } })) };

    expect(layoutGraph(moved).nodes.map((node) => node.position)).toEqual(first.nodes.map((node) => node.position));
  });

  it("supports disconnected nodes, cycles and multiple relationships between the same concepts", () => {
    const map = smallMap();
    map.nodes.push({ ...map.nodes[1], id: "isolated", data: { ...map.nodes[1].data, label: "Isolado" } });
    map.edges.push({ ...map.edges[0], id: "second-relation", label: "outra relação" });
    map.edges.push({ ...map.edges[0], id: "return", source: "topic-1", target: "root" });

    const graph = layoutGraph(adaptMindMap(map));

    expect(graph.nodes).toHaveLength(3);
    expect(graph.edges).toHaveLength(3);
    expect(graph.nodes.every((node) => Number.isFinite(node.position.x) && Number.isFinite(node.position.y))).toBe(true);
  });

  it("does not retain nodes from previous layout calculations", () => {
    layoutGraph(adaptMindMap(smallMap()));
    const map = smallMap();
    map.nodes = [map.nodes[0]];
    map.edges = [];

    const graph = layoutGraph(adaptMindMap(map));

    expect(graph.nodes).toHaveLength(1);
    expect(graph.edges).toEqual([]);
  });

  it("handles an empty graph without producing invalid coordinates", () => {
    expect(layoutGraph({ nodes: [], edges: [] })).toEqual({ nodes: [], edges: [] });
  });
});

describe("layoutGraph for mind map trees", () => {
  it("places the study axes left to right in their numbered order, whatever the API order", () => {
    const map = createMapResponse();
    map.nodes.reverse();
    map.edges.reverse();

    const graph = layoutGraph(adaptMindMap(map));
    const x = (id: string) => graph.nodes.find((node) => node.id === id)!.position.x;
    const y = (id: string) => graph.nodes.find((node) => node.id === id)!.position.y;

    expect(x("topic-1")).toBeLessThan(x("topic-2"));
    expect(y("topic-1")).toBe(y("topic-2"));
    expect(y("chlorophyll")).toBeGreaterThan(y("topic-1"));
    expect(y("leaf")).toBeGreaterThan(y("chlorophyll"));
  });

  it("centers each parent over its children without overlapping subtrees", () => {
    const graph = layoutGraph(adaptMindMap(createMapResponse()));
    const node = (id: string) => graph.nodes.find((item) => item.id === id)!;
    const center = (id: string) => node(id).position.x + node(id).width! / 2;

    expect(center("topic-1")).toBeCloseTo(center("chlorophyll"));
    expect(node("topic-2").position.x).toBeGreaterThanOrEqual(node("topic-1").position.x + node("topic-1").width!);
    expect(center("root")).toBeCloseTo((center("topic-1") + center("topic-2")) / 2);
  });
});
