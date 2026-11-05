import { beforeEach, describe, expect, it, vi } from "vitest";
import { MAX_PDF_SIZE_BYTES } from "../schemas";
import { ingestDocument } from "./ingest-document";

const response = { document_id: "8b6f2a51-3c0e-4f43-9a7d-5d2c1f0e9a11", page_count: 1, document_name: "material_academico.pdf", total_chunks: 3, message: "Successfully ingested." };
const pdf = () => new File(["%PDF-1.4 sample"], "material acadêmico.pdf", { type: "application/pdf" });

beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000"));

describe("ingestDocument", () => {
  it("sends one multipart file and returns the canonical server filename", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json(response, { status: 201 }));
    vi.stubGlobal("fetch", fetch);
    const file = pdf();

    await expect(ingestDocument(file)).resolves.toEqual(response);

    const [url, options] = fetch.mock.calls[0];

    expect(url).toBe("http://localhost:8000/api/documents/ingest");
    expect(options.method).toBe("POST");
    expect(options.body.get("file")).toBe(file);
    expect([...options.body.keys()]).toEqual(["file"]);
    expect(options.headers.has("Content-Type")).toBe(false);
  });

  it.each(["", "application/pdf", "application/octet-stream"])("accepts a PDF with MIME type '%s'", async (type) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));

    await expect(ingestDocument(new File(["%PDF"], "SAMPLE.PDF", { type }))).resolves.toEqual(response);
  });

  it.each([
    ["notes.txt", "application/pdf", "text"],
    ["sample.pdf", "text/plain", "%PDF"],
    ["sample.pdf", "application/pdf", ""],
  ])("rejects invalid file metadata before calling the API (%s, %s)", async (name, type, content) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    await expect(ingestDocument(new File([content], name, { type }))).rejects.toMatchObject({ kind: "validation" });

    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects PDFs larger than 20 MiB before upload", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const file = pdf();
    Object.defineProperty(file, "size", { value: MAX_PDF_SIZE_BYTES + 1 });

    await expect(ingestDocument(file)).rejects.toMatchObject({ kind: "validation" });

    expect(fetch).not.toHaveBeenCalled();
  });

  it("accepts the 20 MiB boundary", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));
    const file = pdf();
    Object.defineProperty(file, "size", { value: MAX_PDF_SIZE_BYTES });

    await expect(ingestDocument(file)).resolves.toEqual(response);
  });

  it.each([
    { ...response, document_name: " " },
    { ...response, total_chunks: -1 },
    { ...response, total_chunks: 1.5 },
    { ...response, total_chunks: "3" },
    { document_id: "8b6f2a51-3c0e-4f43-9a7d-5d2c1f0e9a11", page_count: 1, document_name: response.document_name, total_chunks: 3 },
  ])("rejects a response that violates the document contract", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(body)));

    await expect(ingestDocument(pdf())).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it("does not mark a document without extracted chunks as ready", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ...response, total_chunks: 0 })));

    await expect(ingestDocument(pdf())).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it.each([400, 422])("explains ingestion rejection (%s) without showing raw server details", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "sensitive technical details" }, { status })));

    const error = await ingestDocument(pdf()).catch((error) => error);

    expect(error).toMatchObject({ kind: "http", status });
    expect(error.message).not.toContain("sensitive");
  });
});

describe("ingestDocument service availability", () => {
  it("explains an unavailable AI service without exposing the server detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Ollama embedding model unavailable" }, { status: 503 })));

    await expect(ingestDocument(pdf())).rejects.toMatchObject({
      kind: "http",
      status: 503,
      message: "O serviço de IA está indisponível. Tente enviar o PDF novamente em instantes.",
    });
  });

  it("rejects a response without the document identifier used by the map and the tutor", async () => {
    const withoutId: Partial<typeof response> = { ...response };
    delete withoutId.document_id;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(withoutId)));

    await expect(ingestDocument(pdf())).rejects.toMatchObject({ kind: "invalid-response" });
  });
});
