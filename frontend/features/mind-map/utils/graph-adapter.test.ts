import { describe, expect, it } from "vitest";
import { createMapResponse } from "../test-fixtures";
import { CONCEPT_NODE_SIZE } from "../graph-config";
import { adaptMindMap } from "./graph-adapter";

describe("adaptMindMap", () => {
  it("preserves concept data and the directed relationships returned by the API", () => {
    const map = createMapResponse();
    const graph = adaptMindMap(map);

    expect(graph.nodes.map((node) => node.id)).toEqual(map.nodes.map((node) => node.id));

    graph.nodes.forEach((node, index) => {
      expect(node.data).toMatchObject(map.nodes[index].data);
      expect(node.width).toBe(CONCEPT_NODE_SIZE.width);
      expect(node.height).toBe(CONCEPT_NODE_SIZE.height);
    });

    graph.edges.forEach((edge, index) => {
      expect(edge).toMatchObject({
        id: map.edges[index].id,
        source: map.edges[index].source,
        target: map.edges[index].target,
        label: map.edges[index].label,
        deletable: false,
        reconnectable: false,
      });
    });
  });

  it("maps arbitrary API types to the registered concept component", () => {
    const map = createMapResponse();
    map.nodes[1].type = "unregistered-model-type";
    map.nodes[1].data.category = "root";

    const graph = adaptMindMap(map);

    expect(graph.nodes.every((node) => node.type === "concept")).toBe(true);
    expect(graph.nodes[0].data.isRoot).toBe(true);
    expect(graph.nodes[1].data.isRoot).toBe(true);
  });

  it("does not share mutable node data or positions with the HTTP response", () => {
    const map = createMapResponse();
    const before = structuredClone(map);
    const graph = adaptMindMap(map);

    graph.nodes[0].position.x = 999;
    graph.nodes[0].data.label = "Changed in the view";
    graph.edges[0].label = "Changed in the view";

    expect(map).toEqual(before);
  });
});
