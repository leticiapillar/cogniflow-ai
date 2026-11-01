import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMapResponse, sampleRequest } from "../test-fixtures";
import type { GenerateMapRequest, GenerateMapResponse } from "../types";
import { generateMindMap } from "./generate-mind-map";

beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000"));

describe("generateMindMap", () => {
  it("posts trimmed JSON scoped to the selected document with the default top_k", async () => {
    const response = createMapResponse();
    const fetch = vi.fn().mockResolvedValue(Response.json(response));
    vi.stubGlobal("fetch", fetch);
    const { query, document_name } = sampleRequest;

    await expect(generateMindMap({ query: `  ${query}  `, document_name })).resolves.toEqual(response);

    const [url, options] = fetch.mock.calls[0];

    expect(url).toBe("http://localhost:8000/api/generate-map");
    expect(options.method).toBe("POST");
    expect(options.headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual(sampleRequest);
  });

  it.each(["", " ab ", "a".repeat(2001)])("rejects an invalid query before sending a request", async (query) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    await expect(generateMindMap({ ...sampleRequest, query })).rejects.toMatchObject({ kind: "validation" });

    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([0, 21, 1.5])("rejects invalid top_k (%s) before sending a request", async (top_k) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    await expect(generateMindMap({ ...sampleRequest, top_k })).rejects.toMatchObject({ kind: "validation" });

    expect(fetch).not.toHaveBeenCalled();
  });

  it.each(["abc", "a".repeat(2000)])("accepts the query length boundaries", async (query) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(createMapResponse())));

    await expect(generateMindMap({ query })).resolves.toHaveProperty("source_chunks_used", 2);
  });

  it("rejects incorrect runtime input types", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    await expect(generateMindMap({ query: 123 } as unknown as GenerateMapRequest)).rejects.toMatchObject({ kind: "validation" });

    expect(fetch).not.toHaveBeenCalled();
  });

  const invalidGraphs: [string, (map: GenerateMapResponse) => void][] = [
    ["duplicate nodes", (map) => { map.nodes.push({ ...map.nodes[0] }); }],
    ["duplicate edges", (map) => { map.edges.push({ ...map.edges[0] }); }],
    ["missing source", (map) => { map.edges[0].source = "missing"; }],
    ["missing target", (map) => { map.edges[0].target = "missing"; }],
    ["self loop", (map) => { map.edges[0].target = map.edges[0].source; }],
    ["empty graph", (map) => { map.nodes = []; }],
    ["invalid position", (map) => { map.nodes[0].position.x = Infinity; }],
    ["empty label", (map) => { map.nodes[0].data.label = " "; }],
    ["negative latency", (map) => { map.generation_latency_ms = -1; }],
    ["fractional chunk count", (map) => { map.source_chunks_used = 0.5; }],
  ];
  it.each(invalidGraphs)("rejects a structurally invalid response: %s", async (_description, invalidate) => {
    const response = createMapResponse();
    invalidate(response);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));

    await expect(generateMindMap(sampleRequest)).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it("requires latency metadata rather than silently using the old frontend contract", async () => {
    const response = { ...createMapResponse(), generation_latency_ms: undefined };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));

    await expect(generateMindMap(sampleRequest)).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it("accepts a single isolated concept and nullable optional fields", async () => {
    const response = createMapResponse();
    response.nodes = [response.nodes[0]];
    response.edges = [];
    response.nodes[0].data.summary = null;
    response.nodes[0].data.category = null;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));

    await expect(generateMindMap(sampleRequest)).resolves.toEqual(response);
  });

  it("preserves zero retrieved chunks so the interface can explain absent context", async () => {
    const response = { ...createMapResponse(), source_chunks_used: 0 };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));

    await expect(generateMindMap(sampleRequest)).resolves.toHaveProperty("source_chunks_used", 0);
  });

  it.each([422, 502, 500])("normalizes HTTP %s without displaying raw server information or retrying", async (status) => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ detail: "private server configuration" }, { status }));
    vi.stubGlobal("fetch", fetch);

    const error = await generateMindMap(sampleRequest).catch((error) => error);

    expect(error).toMatchObject({ kind: "http", status });
    expect(error.message).not.toContain("private");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
