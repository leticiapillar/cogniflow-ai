import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/services/http-client";
import { generateMindMap } from "../services/generate-mind-map";
import { createMapResponse, sampleRequest } from "../test-fixtures";
import type { GenerateMapResponse } from "../types";
import { useGenerateMindMap } from "./use-generate-mind-map";

vi.mock("../services/generate-mind-map", () => ({ generateMindMap: vi.fn() }));

const generate = vi.mocked(generateMindMap);

function deferred() {
  let resolve!: (map: GenerateMapResponse) => void;
  const promise = new Promise<GenerateMapResponse>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => generate.mockReset());
afterEach(cleanup);

describe("useGenerateMindMap", () => {
  it("requires a document and a valid trimmed query", async () => {
    const { result } = renderHook(useGenerateMindMap);

    await act(() => result.current.generate());

    expect(result.current.state).toMatchObject({ status: "error", error: { kind: "validation" } });

    act(() => result.current.updateQuery(" ab "));
    await act(() => result.current.generate("biologia.pdf"));

    expect(result.current.state).toMatchObject({ status: "error", error: { kind: "validation" } });
    expect(generate).not.toHaveBeenCalled();
  });

  it("blocks synchronous duplicate requests and associates the response with its original request", async () => {
    const pending = deferred();
    generate.mockReturnValue(pending.promise);

    const { result } = renderHook(useGenerateMindMap);

    act(() => result.current.updateQuery(` ${sampleRequest.query} `));
    let first!: Promise<void>;
    act(() => { first = result.current.generate("biologia.pdf"); void result.current.generate("biologia.pdf"); });

    expect(generate).toHaveBeenCalledTimes(1);
    expect(result.current.state).toEqual({ status: "generating", request: sampleRequest });

    const map = createMapResponse();
    await act(async () => { pending.resolve(map); await first; });

    expect(result.current.state).toEqual({ status: "success", request: sampleRequest, map });
  });

  it("aborts on query changes and ignores late responses without clearing a newer request", async () => {
    const old = deferred();
    const current = deferred();
    generate.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);

    const { result } = renderHook(useGenerateMindMap);

    act(() => result.current.updateQuery("Primeira consulta"));
    let first!: Promise<void>;
    act(() => { first = result.current.generate("biologia.pdf"); });
    const signal = generate.mock.calls[0][1]?.signal;
    act(() => result.current.updateQuery("Segunda consulta"));

    expect(signal?.aborted).toBe(true);

    let second!: Promise<void>;
    act(() => { second = result.current.generate("biologia.pdf"); });
    await act(async () => { old.resolve(createMapResponse()); await first; });

    expect(result.current.state.status).toBe("generating");

    await act(() => result.current.generate("biologia.pdf"));

    expect(generate).toHaveBeenCalledTimes(2);

    const map = { ...createMapResponse(), topic: "Novo resultado" };
    await act(async () => { current.resolve(map); await second; });

    expect(result.current.state).toMatchObject({ status: "success", request: { query: "Segunda consulta" }, map });
  });

  it("clears results on document reset while preserving the query", async () => {
    generate.mockResolvedValue(createMapResponse());

    const { result } = renderHook(useGenerateMindMap);

    act(() => result.current.updateQuery(sampleRequest.query));
    await act(() => result.current.generate("biologia.pdf"));
    act(() => result.current.reset());

    expect(result.current.state.status).toBe("idle");
    expect(result.current.query).toBe(sampleRequest.query);
  });

  it("cancels and discards late responses while preserving the query", async () => {
    const pending = deferred();
    generate.mockReturnValue(pending.promise);

    const { result } = renderHook(useGenerateMindMap);

    act(() => result.current.updateQuery(sampleRequest.query));
    let request!: Promise<void>;
    act(() => { request = result.current.generate("biologia.pdf"); });
    act(() => result.current.cancel());

    expect(generate.mock.calls[0][1]?.signal?.aborted).toBe(true);

    await act(async () => { pending.resolve(createMapResponse()); await request; });

    expect(result.current.state.status).toBe("idle");
    expect(result.current.query).toBe(sampleRequest.query);
  });

  it("aborts on unmount", async () => {
    const pending = deferred();
    generate.mockReturnValue(pending.promise);

    const { result, unmount } = renderHook(useGenerateMindMap);

    act(() => result.current.updateQuery(sampleRequest.query));
    let request!: Promise<void>;
    act(() => { request = result.current.generate("biologia.pdf"); });
    unmount();

    expect(generate.mock.calls[0][1]?.signal?.aborted).toBe(true);

    pending.resolve(createMapResponse());
    await request;
  });

  it.each(["network", "timeout", "invalid-response"] as const)("preserves the query after %s and allows retry", async (kind) => {
    generate.mockRejectedValueOnce(new ApiError(kind, "Tente novamente."))
      .mockResolvedValueOnce(createMapResponse());

    const { result } = renderHook(useGenerateMindMap);

    act(() => result.current.updateQuery(sampleRequest.query));
    await act(() => result.current.generate("biologia.pdf"));

    expect(result.current.state).toMatchObject({ status: "error", error: { kind } });
    expect(result.current.query).toBe(sampleRequest.query);

    await act(() => result.current.generate("biologia.pdf"));

    expect(result.current.state.status).toBe("success");
  });
});
