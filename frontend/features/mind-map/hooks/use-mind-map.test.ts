import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/services/http-client";
import { getMindMapStatus, regenerateMindMap, retryMindMapSection } from "../services/mind-map-api";
import { createProcessingStatus, createStatusResponse, DOCUMENT_ID } from "../test-fixtures";
import { POLL_INTERVAL_MS, useMindMap } from "./use-mind-map";

vi.mock("../services/mind-map-api", () => ({
  getMindMapStatus: vi.fn(),
  regenerateMindMap: vi.fn(),
  retryMindMapSection: vi.fn(),
}));

const getStatus = vi.mocked(getMindMapStatus);
const regenerate = vi.mocked(regenerateMindMap);
const retry = vi.mocked(retryMindMapSection);

beforeEach(() => {
  vi.useFakeTimers();
  getStatus.mockReset();
  regenerate.mockReset();
  retry.mockReset();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const flush = () => act(async () => { await Promise.resolve(); });
const tick = () => act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS); });

describe("useMindMap", () => {
  it("stays idle without a document", () => {
    const { result } = renderHook(() => useMindMap(null));

    expect(result.current.state).toEqual({ status: "idle" });
    expect(getStatus).not.toHaveBeenCalled();
  });

  it("polls while the map is generated and stops when it is ready", async () => {
    getStatus
      .mockResolvedValueOnce(createProcessingStatus(0, 2))
      .mockResolvedValueOnce(createProcessingStatus(1, 2))
      .mockResolvedValueOnce(createStatusResponse());

    const { result } = renderHook(() => useMindMap(DOCUMENT_ID));
    expect(result.current.state.status).toBe("loading");

    await flush();
    expect(result.current.state).toMatchObject({ status: "generating", response: { progress: { done: 0 } } });

    await tick();
    expect(result.current.state).toMatchObject({ status: "generating", response: { progress: { done: 1 } } });

    await tick();
    expect(result.current.state).toMatchObject({ status: "ready", map: { topic: "Fotossíntese" } });

    await tick();
    expect(getStatus).toHaveBeenCalledTimes(3);
  });

  it("reports a missing map and generates it on demand", async () => {
    getStatus.mockRejectedValueOnce(new ApiError("http", "Sem mapa.", 404)).mockResolvedValue(createStatusResponse());
    regenerate.mockResolvedValue(createStatusResponse({ status: "pending", mind_map: null }));

    const { result } = renderHook(() => useMindMap(DOCUMENT_ID));
    await flush();
    expect(result.current.state).toEqual({ status: "missing" });

    act(() => result.current.regenerate());
    expect(result.current.state.status).toBe("loading");
    await flush();
    expect(result.current.state.status).toBe("generating");

    await tick();
    expect(result.current.state.status).toBe("ready");
  });

  it("keeps following a generation that is already running (409)", async () => {
    getStatus.mockResolvedValueOnce(createStatusResponse({ status: "partial", failed_sections: [{ section_index: 1, section_title: "Calvin", reason: "x" }] }))
      .mockResolvedValue(createStatusResponse());
    retry.mockRejectedValue(new ApiError("http", "Em andamento.", 409));

    const { result } = renderHook(() => useMindMap(DOCUMENT_ID));
    await flush();
    expect(result.current.state.status).toBe("ready");

    act(() => result.current.retrySection(1));
    await flush();
    expect(retry).toHaveBeenCalledWith(DOCUMENT_ID, 1, expect.anything());

    await tick();
    expect(result.current.state).toMatchObject({ status: "ready", response: { failed_sections: [] } });
  });

  it("exposes failures and request errors", async () => {
    getStatus.mockResolvedValueOnce(createStatusResponse({ status: "failed", mind_map: null, error: "down" }))
      .mockRejectedValueOnce(new ApiError("network", "Sem conexão."));

    const { result } = renderHook(() => useMindMap(DOCUMENT_ID));
    await flush();
    expect(result.current.state.status).toBe("failed");

    act(() => result.current.refresh());
    await flush();
    expect(result.current.state).toMatchObject({ status: "error", error: { message: "Sem conexão." } });
  });

  it("stops polling and ignores late answers when the document changes", async () => {
    let resolveFirst!: (value: ReturnType<typeof createProcessingStatus>) => void;
    getStatus.mockReturnValueOnce(new Promise((done) => { resolveFirst = done; }));

    const { result, rerender } = renderHook(({ id }) => useMindMap(id), { initialProps: { id: DOCUMENT_ID as string | null } });
    const signal = getStatus.mock.calls[0][1]?.signal;

    rerender({ id: null });
    expect(signal?.aborted).toBe(true);

    await act(async () => { resolveFirst(createProcessingStatus()); });
    await tick();

    expect(result.current.state).toEqual({ status: "idle" });
    expect(getStatus).toHaveBeenCalledTimes(1);
  });
});
