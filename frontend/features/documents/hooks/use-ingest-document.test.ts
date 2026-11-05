import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/services/http-client";
import { ingestDocument } from "../services/ingest-document";
import type { DocumentUploadResponse } from "../types";
import { useIngestDocument } from "./use-ingest-document";

vi.mock("../services/ingest-document", () => ({ ingestDocument: vi.fn() }));

const ingest = vi.mocked(ingestDocument);
const document = { document_id: "8b6f2a51-3c0e-4f43-9a7d-5d2c1f0e9a11", page_count: 1, document_name: "canonical.pdf", total_chunks: 2, message: "Ingested." };
const pdf = (name = "material.pdf") => new File(["%PDF"], name, { type: "application/pdf" });

function deferred() {
  let resolve!: (value: DocumentUploadResponse) => void;
  const promise = new Promise<DocumentUploadResponse>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => ingest.mockReset());
afterEach(cleanup);

describe("useIngestDocument", () => {
  it("validates selection without sending an invalid file", async () => {
    const onChange = vi.fn();

    const { result } = renderHook(() => useIngestDocument(onChange));

    act(() => result.current.selectFile(pdf("notes.txt")));

    expect(result.current.state).toMatchObject({ status: "error", error: { kind: "validation" } });

    await act(() => result.current.upload());

    expect(ingest).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalledWith(document);
  });

  it("blocks duplicate submissions and publishes the canonical document", async () => {
    const pending = deferred();
    ingest.mockReturnValue(pending.promise);
    const onChange = vi.fn();

    const { result } = renderHook(() => useIngestDocument(onChange));

    act(() => result.current.selectFile(pdf()));
    let first!: Promise<void>;
    act(() => { first = result.current.upload(); void result.current.upload(); });

    expect(ingest).toHaveBeenCalledTimes(1);
    expect(result.current.state.status).toBe("uploading");

    await act(async () => { pending.resolve(document); await first; });

    expect(result.current.state).toEqual({ status: "success", document });
    expect(onChange).toHaveBeenLastCalledWith(document);
  });

  it("aborts replaced uploads and ignores their late response", async () => {
    const old = deferred();
    const current = deferred();
    ingest.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const onChange = vi.fn();

    const { result } = renderHook(() => useIngestDocument(onChange));

    act(() => result.current.selectFile(pdf("old.pdf")));
    let first!: Promise<void>;
    act(() => { first = result.current.upload(); });
    const signal = ingest.mock.calls[0][1]?.signal;

    act(() => result.current.selectFile(pdf("new.pdf")));

    expect(signal?.aborted).toBe(true);

    let second!: Promise<void>;
    act(() => { second = result.current.upload(); });
    await act(async () => { current.resolve(document); await second; });
    await act(async () => { old.resolve({ ...document, document_name: "old.pdf" }); await first; });

    expect(result.current.state).toEqual({ status: "success", document });
    expect(onChange).toHaveBeenLastCalledWith(document);
  });

  it("cancels without losing the selected file and ignores a late response", async () => {
    const pending = deferred();
    ingest.mockReturnValue(pending.promise);
    const onChange = vi.fn();

    const { result } = renderHook(() => useIngestDocument(onChange));

    const file = pdf();
    act(() => result.current.selectFile(file));
    let request!: Promise<void>;
    act(() => { request = result.current.upload(); });
    act(() => result.current.cancel());

    expect(ingest.mock.calls[0][1]?.signal?.aborted).toBe(true);

    await act(async () => { pending.resolve(document); await request; });

    expect(result.current.state.status).toBe("idle");
    expect(result.current.selectedFile).toBe(file);
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("aborts on unmount without publishing a late document", async () => {
    const pending = deferred();
    ingest.mockReturnValue(pending.promise);
    const onChange = vi.fn();

    const { result, unmount } = renderHook(() => useIngestDocument(onChange));

    act(() => result.current.selectFile(pdf()));
    let request!: Promise<void>;
    act(() => { request = result.current.upload(); });
    unmount();

    expect(ingest.mock.calls[0][1]?.signal?.aborted).toBe(true);

    pending.resolve(document);
    await request;

    expect(onChange).not.toHaveBeenCalledWith(document);
  });

  it("preserves selection after failure and allows retry", async () => {
    ingest.mockRejectedValueOnce(new ApiError("network", "Falha de conexão.")).mockResolvedValueOnce(document);

    const { result } = renderHook(() => useIngestDocument(vi.fn()));

    const file = pdf();
    act(() => result.current.selectFile(file));
    await act(() => result.current.upload());

    expect(result.current.state.status).toBe("error");
    expect(result.current.selectedFile).toBe(file);

    await act(() => result.current.upload());

    expect(result.current.state).toEqual({ status: "success", document });
  });
});
