import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ingestDocument } from "@/features/documents/services/ingest-document";
import { getMindMapStatus } from "@/features/mind-map/services/mind-map-api";
import { createProcessingStatus, createStatusResponse, DOCUMENT_ID } from "@/features/mind-map/test-fixtures";
import { getServiceHealth } from "@/features/service-status/services/get-service-health";
import { askTutor } from "@/features/tutor/services/ask-tutor";
import { createAnswer } from "@/features/tutor/test-fixtures";
import { StudyWorkspace } from "./study-workspace";

vi.mock("@/features/documents/services/ingest-document", () => ({ ingestDocument: vi.fn() }));
vi.mock("@/features/mind-map/services/mind-map-api", () => ({
  getMindMapStatus: vi.fn(), regenerateMindMap: vi.fn(), retryMindMapSection: vi.fn(),
}));
vi.mock("@/features/service-status/services/get-service-health", () => ({ getServiceHealth: vi.fn() }));
vi.mock("@/features/tutor/services/ask-tutor", () => ({ askTutor: vi.fn() }));
vi.mock("@/features/mind-map/components/mind-map-viewer", () => ({
  MindMapViewer: ({ map, onAskAbout }: { map: { nodes: { id: string; data: { label: string } }[] }; onAskAbout?: (node: unknown) => void }) => (
    <div data-testid="map-canvas">
      <button onClick={() => onAskAbout?.(map.nodes.find((node) => node.id === "chlorophyll"))}>Tirar dúvida sobre este conceito</button>
    </div>
  ),
}));

const ingest = vi.mocked(ingestDocument);
const status = vi.mocked(getMindMapStatus);
const health = vi.mocked(getServiceHealth);
const ask = vi.mocked(askTutor);
const healthy = { status: "healthy" as const, database_connected: true, ollama_connected: true, issues: [] };

beforeEach(() => {
  vi.useFakeTimers();
  health.mockReset().mockResolvedValue(healthy);
  ingest.mockReset().mockResolvedValue({
    document_id: DOCUMENT_ID, document_name: "biologia.pdf", page_count: 3, total_chunks: 2, message: "Ingested.",
  });
  status.mockReset();
  ask.mockReset();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

async function upload() {
  fireEvent.change(screen.getByLabelText("Arquivo PDF"), {
    target: { files: [new File(["%PDF"], "biologia.pdf", { type: "application/pdf" })] },
  });
  await act(async () => { fireEvent.submit(screen.getByRole("form", { name: "Envio de material de estudo" })); });
}

it("blocks the upload while the AI service is unavailable", async () => {
  health.mockResolvedValue({ ...healthy, status: "degraded", ollama_connected: false });
  render(<StudyWorkspace />);
  await act(async () => {});

  expect(screen.getByText("O serviço de IA está iniciando ou indisponível.")).toBeTruthy();
  expect((screen.getByLabelText("Arquivo PDF") as HTMLInputElement).disabled).toBe(true);

  health.mockResolvedValue(healthy);
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Verificar novamente" })); });

  expect(screen.queryByText("O serviço de IA está iniciando ou indisponível.")).toBeNull();
  expect((screen.getByLabelText("Arquivo PDF") as HTMLInputElement).disabled).toBe(false);
});

it("follows the map generation after the upload and only then enables the tutor", async () => {
  status.mockResolvedValueOnce(createProcessingStatus(0, 2)).mockResolvedValueOnce(createStatusResponse());
  render(<StudyWorkspace />);
  await act(async () => {});

  await upload();

  expect(status).toHaveBeenCalledWith(DOCUMENT_ID, expect.anything());
  expect(screen.getByText("Lendo a seção 1 de 2: Cloroplastos.")).toBeTruthy();
  expect(screen.getByLabelText("Sua dúvida").closest("fieldset")?.disabled).toBe(true);

  await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });

  expect(screen.getByTestId("map-canvas")).toBeTruthy();
  expect(screen.getByLabelText("Sua dúvida").closest("fieldset")?.disabled).toBe(false);
});

it("asks the tutor about a concept selected in the map", async () => {
  status.mockResolvedValue(createStatusResponse());
  ask.mockResolvedValue(createAnswer());
  render(<StudyWorkspace />);
  await act(async () => {});
  await upload();

  fireEvent.click(screen.getByRole("button", { name: "Tirar dúvida sobre este conceito" }));

  expect(document.activeElement).toBe(screen.getByLabelText("Sua dúvida"));
  expect(screen.getByText(/Dúvida sobre o conceito:/).textContent).toContain("Clorofila");

  fireEvent.change(screen.getByLabelText("Sua dúvida"), { target: { value: "O que ela faz?" } });
  await act(async () => { fireEvent.submit(screen.getByRole("form", { name: "Pergunta para o tutor" })); });

  expect(ask).toHaveBeenCalledWith(DOCUMENT_ID, expect.objectContaining({ node_id: "chlorophyll" }), expect.anything());
  expect(screen.getByRole("article", { name: "Resposta do tutor" })).toBeTruthy();
});

it("clears the map and the conversation when the material is replaced", async () => {
  status.mockResolvedValue(createStatusResponse());
  ask.mockResolvedValue(createAnswer());
  render(<StudyWorkspace />);
  await act(async () => {});
  await upload();

  fireEvent.change(screen.getByLabelText("Sua dúvida"), { target: { value: "O que é a clorofila?" } });
  await act(async () => { fireEvent.submit(screen.getByRole("form", { name: "Pergunta para o tutor" })); });
  expect(screen.getByRole("list", { name: "Conversa com o tutor" })).toBeTruthy();

  fireEvent.change(screen.getByLabelText("Arquivo PDF"), {
    target: { files: [new File(["%PDF changed"], "outro.pdf", { type: "application/pdf" })] },
  });

  expect(screen.queryByTestId("map-canvas")).toBeNull();
  expect(screen.queryByRole("list", { name: "Conversa com o tutor" })).toBeNull();
  expect(screen.getByLabelText("Sua dúvida").closest("fieldset")?.disabled).toBe(true);
});
