import { beforeEach, describe, expect, it, vi } from "vitest";
import { createStatusResponse, DOCUMENT_ID } from "../test-fixtures";
import { getMindMapStatus, regenerateMindMap, retryMindMapSection } from "./mind-map-api";

beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000"));

describe("mind map API", () => {
  it("reads the status of the document's map", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json(createStatusResponse()));
    vi.stubGlobal("fetch", fetch);

    const status = await getMindMapStatus(DOCUMENT_ID);

    expect(fetch.mock.calls[0][0]).toBe(`http://localhost:8000/api/documents/${DOCUMENT_ID}/mind-map`);
    expect(status.status).toBe("ready");
    expect(status.mind_map?.nodes).toHaveLength(6);
  });

  it("requests a regeneration and a section retry with POST", async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(Response.json(createStatusResponse({ status: "pending", mind_map: null }), { status: 202 })));
    vi.stubGlobal("fetch", fetch);

    await regenerateMindMap(DOCUMENT_ID);
    await retryMindMapSection(DOCUMENT_ID, 3);

    expect(fetch.mock.calls.map(([url, options]) => [url, options.method])).toEqual([
      [`http://localhost:8000/api/documents/${DOCUMENT_ID}/mind-map/regenerate`, "POST"],
      [`http://localhost:8000/api/documents/${DOCUMENT_ID}/mind-map/sections/3/retry`, "POST"],
    ]);
  });

  it.each([
    [404, "Este material ainda não tem um mapa mental."],
    [409, "Já existe uma geração em andamento para este material."],
  ])("translates HTTP %s into a literal message", async (status, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "server detail" }, { status })));

    await expect(getMindMapStatus(DOCUMENT_ID)).rejects.toMatchObject({ kind: "http", status, message });
  });

  it("rejects a ready status without the map", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(createStatusResponse({ mind_map: null }))));

    await expect(getMindMapStatus(DOCUMENT_ID)).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it("rejects a map with a dangling relation", async () => {
    const response = createStatusResponse();
    response.mind_map!.edges[0].target = "missing";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));

    await expect(getMindMapStatus(DOCUMENT_ID)).rejects.toMatchObject({ kind: "invalid-response" });
  });
});
