import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ingestDocument } from "@/features/documents/services/ingest-document";
import { generateMindMap } from "@/features/mind-map/services/generate-mind-map";
import { createMapResponse, sampleRequest } from "@/features/mind-map/test-fixtures";
import type { GenerateMapResponse } from "@/features/mind-map/types";
import { StudyWorkspace } from "./study-workspace";

vi.mock("@/features/documents/services/ingest-document", () => ({ ingestDocument: vi.fn() }));
vi.mock("@/features/mind-map/services/generate-mind-map", () => ({ generateMindMap: vi.fn() }));
vi.mock("@/features/mind-map/components/mind-map-viewer", () => ({ MindMapViewer: () => <div data-testid="map-canvas" /> }));
const ingest = vi.mocked(ingestDocument);
const generate = vi.mocked(generateMindMap);

beforeEach(() => {
  ingest.mockReset().mockResolvedValue({ document_name: "biologia.pdf", total_chunks: 2, message: "Ingested." });
  generate.mockReset();
});

afterEach(cleanup);

async function prepareDocument() {
  fireEvent.change(screen.getByLabelText("Arquivo PDF"), {
    target: { files: [new File(["%PDF"], "biologia.pdf", { type: "application/pdf" })] },
  });

  await act(async () => { fireEvent.submit(screen.getByRole("form", { name: "Envio de material de estudo" })); });

  fireEvent.change(screen.getByLabelText("O que você quer estudar?"), { target: { value: sampleRequest.query } });
}

it("connects ingestion to generation and clears results when replacing even the same filename", async () => {
  generate.mockResolvedValue(createMapResponse());

  render(<StudyWorkspace />);

  await prepareDocument();

  expect(document.activeElement).toBe(screen.getByLabelText("O que você quer estudar?"));

  await act(async () => { fireEvent.submit(screen.getByRole("form", { name: "Geração de mapa mental" })); });

  expect(generate).toHaveBeenCalledWith(sampleRequest, expect.objectContaining({ signal: expect.any(AbortSignal) }));
  expect(screen.getByTestId("map-canvas")).toBeTruthy();

  fireEvent.change(screen.getByLabelText("Arquivo PDF"), {
    target: { files: [new File(["%PDF changed"], "biologia.pdf", { type: "application/pdf" })] },
  });

  expect(screen.queryByTestId("map-canvas")).toBeNull();
  expect(screen.getByLabelText("O que você quer estudar?").closest("fieldset")?.disabled).toBe(true);
  expect((screen.getByLabelText("O que você quer estudar?") as HTMLTextAreaElement).value).toBe(sampleRequest.query);
});

it("ignores generation responses arriving after a document replacement", async () => {
  let resolve!: (value: GenerateMapResponse) => void;

  generate.mockReturnValue(new Promise((done) => { resolve = done; }));

  render(<StudyWorkspace />);

  await prepareDocument();

  fireEvent.submit(screen.getByRole("form", { name: "Geração de mapa mental" }));

  const signal = generate.mock.calls[0][1]?.signal;

  fireEvent.change(screen.getByLabelText("Arquivo PDF"), {
    target: { files: [new File(["%PDF"], "outro.pdf", { type: "application/pdf" })] },
  });

  expect(signal?.aborted).toBe(true);

  await act(async () => { resolve(createMapResponse()); });

  expect(screen.queryByTestId("map-canvas")).toBeNull();
});
