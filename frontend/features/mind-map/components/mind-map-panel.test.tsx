import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useExpansionContext } from "../expansion";
import { createMapResponse, createProcessingStatus, createStatusResponse } from "../test-fixtures";
import type { MindMapState } from "../types";
import { MindMapPanel } from "./mind-map-panel";

vi.mock("./mind-map-viewer", () => ({
  MindMapViewer: function Viewer({ onShowList }: { onShowList?: () => void }) {
    const expansion = useExpansionContext();
    return <div data-testid="map-canvas">
      <span data-testid="canvas-open">{[...(expansion?.expanded ?? [])].join(",")}</span>
      <button onClick={onShowList}>Simular falha do canvas</button>
    </div>;
  },
}));

afterEach(cleanup);

const actions = () => ({ onRefresh: vi.fn(), onRegenerate: vi.fn(), onRetrySection: vi.fn() });
const ready = (response = createStatusResponse()): MindMapState => ({ status: "ready", response, map: response.mind_map! });

it("announces the literal progress and the three fixed steps while generating", () => {
  render(<MindMapPanel state={{ status: "generating", response: createProcessingStatus(1, 3) }} {...actions()} />);

  expect(screen.getByRole("status").textContent).toBe("Lendo a seção 2 de 3: Cloroplastos.");
  const steps = screen.getByRole("list", { name: "Etapas da geração do mapa" });
  expect(steps.querySelector("[aria-current='step']")?.textContent).toContain("Ler cada seção do material");
  expect((screen.getByLabelText("Seções lidas: 1 de 3") as HTMLProgressElement).value).toBe(1);
  expect(screen.queryByTestId("map-canvas")).toBeNull();
});

it("shows the map with the material name and the number of axes", () => {
  render(<MindMapPanel state={ready()} {...actions()} />);

  expect(screen.getByRole("status").textContent).toBe("Mapa pronto. Comece pelo Eixo 1.");
  expect(screen.getByText("Material: biologia.pdf")).toBeTruthy();
  expect(screen.getByText("2 eixos de estudo")).toBeTruthy();
  expect(screen.getByTestId("map-canvas")).toBeTruthy();
});

it("lists the sections left out of a partial map, each with its own retry", () => {
  const props = actions();
  const response = createStatusResponse({
    status: "partial",
    failed_sections: [{ section_index: 2, section_title: "Ciclo de Calvin", reason: "invalid" }, { section_index: 4, section_title: null, reason: "x" }],
  });

  render(<MindMapPanel state={ready(response)} {...props} />);

  expect(screen.getByRole("status").textContent).toBe("Mapa pronto. Algumas seções não puderam ser processadas.");
  expect(screen.getByText(/2 seções do material não foram processadas/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Tentar de novo: Seção 5" }));
  expect(props.onRetrySection).toHaveBeenCalledWith(4);
  expect(screen.getByTestId("map-canvas")).toBeTruthy();
});

it("explains a failed map and offers to generate it again", () => {
  const props = actions();
  render(<MindMapPanel state={{ status: "failed", response: createStatusResponse({ status: "failed", mind_map: null }) }} {...props} />);

  expect(screen.getByRole("alert").textContent).toContain("O mapa não foi gerado.");
  fireEvent.click(screen.getByRole("button", { name: "Gerar novamente" }));
  expect(props.onRegenerate).toHaveBeenCalled();
});

it("offers to generate a missing map and to retry a failed query", () => {
  const props = actions();
  const { rerender } = render(<MindMapPanel state={{ status: "missing" }} {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "Gerar mapa" }));
  expect(props.onRegenerate).toHaveBeenCalled();

  rerender(<MindMapPanel state={{ status: "error", error: { message: "Sem conexão." } as never }} {...props} />);
  expect(screen.getByRole("status").textContent).toBe("Sem conexão.");
  fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
  expect(props.onRefresh).toHaveBeenCalled();
});

it("keeps the canvas mounted and the open axes when switching between map and list", () => {
  render(<MindMapPanel state={ready()} {...actions()} />);
  const canvas = screen.getByTestId("map-canvas");

  fireEvent.click(screen.getByRole("button", { name: "Lista" }));
  expect(canvas.closest("[hidden]")).not.toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Abrir eixo 2/ }));
  expect(screen.getByText("Fase clara")).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "Mapa" }));
  expect(screen.getByTestId("map-canvas")).toBe(canvas);
  expect(screen.getByTestId("canvas-open").textContent).toBe("topic-2");

  fireEvent.click(screen.getByRole("button", { name: "Abrir todos os eixos" }));
  expect(screen.getByTestId("canvas-open").textContent).toBe("topic-1,topic-2");
  fireEvent.click(screen.getByRole("button", { name: "Fechar todos os eixos" }));
  expect(screen.getByTestId("canvas-open").textContent).toBe("");
});

it("renders model content as text instead of HTML", () => {
  const response = createStatusResponse();
  response.mind_map!.nodes[0].data.summary = "<script>alert('unsafe')</script>";

  const { container } = render(<MindMapPanel state={ready(response)} {...actions()} />);
  fireEvent.click(screen.getByRole("button", { name: "Lista" }));

  expect(screen.getByText("<script>alert('unsafe')</script>")).toBeTruthy();
  expect(container.querySelector("script")).toBeNull();
});

it("offers a focused textual fallback when the canvas requests recovery", async () => {
  render(<MindMapPanel state={ready()} {...actions()} />);

  fireEvent.click(screen.getByRole("button", { name: "Simular falha do canvas" }));

  const panel = screen.getByRole("region", { name: "Leitura textual do mapa" });
  await waitFor(() => expect(document.activeElement).toBe(panel));
});

it("moves focus to the heading when the map becomes ready", () => {
  const { rerender } = render(<MindMapPanel state={{ status: "generating", response: createProcessingStatus() }} {...actions()} />);
  rerender(<MindMapPanel state={ready({ ...createStatusResponse(), mind_map: createMapResponse() })} {...actions()} />);

  expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Mapa mental da aula" }));
});
