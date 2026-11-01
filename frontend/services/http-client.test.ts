import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { requestJson } from "./http-client";

beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/"));
afterEach(() => vi.useRealTimers());

function pendingFetch() {
  return vi.fn((_url: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  }));
}

describe("requestJson", () => {
  it("uses the configured base URL and preserves multipart headers", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetch);
    const body = new FormData();
    body.append("file", new File(["%PDF"], "sample.pdf"));

    await expect(requestJson("/api/documents/ingest", { method: "POST", body })).resolves.toEqual({ ok: true });

    const [url, options] = fetch.mock.calls[0];

    expect(url).toBe("http://localhost:8000/api/documents/ingest");
    expect(options.body).toBe(body);
    expect(options.headers.get("Accept")).toBe("application/json");
    expect(options.headers.has("Content-Type")).toBe(false);
  });

  it("preserves headers supplied by a JSON service", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetch);

    await requestJson("/api/example", { headers: { "Content-Type": "application/json" } });

    expect(fetch.mock.calls[0][1].headers.get("Content-Type")).toBe("application/json");
  });

  it.each([400, 422, 500, 502])("normalizes HTTP %s without exposing server details or retrying", async (status) => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ detail: "private database password" }, { status }));
    vi.stubGlobal("fetch", fetch);

    const error = await requestJson("/api/example").catch((error) => error);

    expect(error).toMatchObject({ kind: "http", status });
    expect(error).toHaveProperty("message", expect.not.stringContaining("password"));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("rejects malformed successful JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>proxy error</html>")));

    await expect(requestJson("/api/example")).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it("normalizes network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(requestJson("/api/example")).rejects.toMatchObject({ kind: "network" });
  });

  it("does not send an already cancelled request", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();
    controller.abort();

    await expect(requestJson("/api/example", { signal: controller.signal })).rejects.toMatchObject({ kind: "cancelled" });

    expect(fetch).not.toHaveBeenCalled();
  });

  it("forwards cancellation and removes its listener", async () => {
    vi.stubGlobal("fetch", pendingFetch());
    const controller = new AbortController();
    const remove = vi.spyOn(controller.signal, "removeEventListener");
    const promise = requestJson("/api/example", { signal: controller.signal });
    const assertion = expect(promise).rejects.toMatchObject({ kind: "cancelled" });

    controller.abort();
    await assertion;

    expect(remove).toHaveBeenCalledWith("abort", expect.any(Function));
  });

  it("aborts timed out requests and clears the timer", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", pendingFetch());
    const promise = requestJson("/api/example", { timeoutMs: 30 });
    const assertion = expect(promise).rejects.toMatchObject({ kind: "timeout" });

    await vi.advanceTimersByTimeAsync(30);
    await assertion;

    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps the timeout active while reading the response body", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn((_url, options) => Promise.resolve({
      ok: true,
      json: () => new Promise((_resolve, reject) => {
        options.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      }),
    })));
    const promise = requestJson("/api/example", { timeoutMs: 30 });
    const assertion = expect(promise).rejects.toMatchObject({ kind: "timeout" });

    await vi.advanceTimersByTimeAsync(30);
    await assertion;
  });

  it("clears the timeout after success", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ok: true })));

    await requestJson("/api/example");

    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(["", "file:///tmp/api", "http://user:secret@localhost", "http://localhost?key=secret"])("rejects invalid configuration: %s", async (url) => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", url);
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    await expect(requestJson("/api/example")).rejects.toMatchObject({ kind: "configuration" });

    expect(fetch).not.toHaveBeenCalled();
  });
});
