import { randomUUID } from "node:crypto";
import { assertLocalApi, readProposalPdf, removeTestDocument } from "@/test-utils/real-api";
import { expect, it, vi } from "vitest";
import { requestJson } from "@/services/http-client";
import { ingestDocument } from "./ingest-document";

it.skipIf(!process.env.COGNIFLOW_INTEGRATION_URL)("ingests a real PDF through FastAPI and retrieves persisted chunks", async () => {
  assertLocalApi(process.env.COGNIFLOW_INTEGRATION_URL!);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", process.env.COGNIFLOW_INTEGRATION_URL);
  const bytes = await readProposalPdf();
  const name = `cogniflow-stage2-${randomUUID()}.pdf`;
  const file = new File([new Uint8Array(bytes)], name, { type: "application/pdf" });

  try {
    const document = await ingestDocument(file);

    expect(document.document_name).toBe(name);
    expect(document.total_chunks).toBeGreaterThan(0);

    const chunks = await requestJson(`/api/documents/${encodeURIComponent(name)}/chunks`);

    expect(Array.isArray(chunks)).toBe(true);
    expect(chunks).toHaveLength(document.total_chunks);
  } finally {
    await removeTestDocument(name);
  }
}, 120_000);
