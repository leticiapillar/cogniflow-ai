import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { createMapResponse, sampleRequest } from "../test-fixtures";
import { MindMapResult } from "./mind-map-result";

vi.mock("./mind-map-viewer", () => ({
  MindMapViewer: ({ onShowList }: { onShowList?: () => void }) => <div data-testid="map-canvas">
    <button onClick={onShowList}>Simular falha do canvas</button>
  </div>,
}));

afterEach(cleanup);

it("presents the concepts with the original document and query", () => {
  render(<MindMapResult state={{ status: "success", request: sampleRequest, map: createMapResponse() }} />);

  fireEvent.click(screen.getByRole("button", { name: "Lista" }));

  expect(screen.getByRole("list", { name: "Conceitos gerados" }).children).toHaveLength(2);
  expect(screen.getByText("Documento: biologia.pdf")).toBeTruthy();
  expect(screen.getByText(`Consulta: ${sampleRequest.query}`)).toBeTruthy();
  expect(screen.getByText("Pigmento que absorve luz.")).toBeTruthy();
});

it("explains absent context without showing ungrounded concepts", () => {
  render(<MindMapResult state={{ status: "success", request: sampleRequest, map: { ...createMapResponse(), source_chunks_used: 0 } }} />);

  expect(screen.getByRole("status").textContent).toContain("Nenhum trecho do documento foi recuperado");
  expect(screen.queryByRole("list", { name: "Conceitos gerados" })).toBeNull();
  expect(screen.queryByText("Clorofila")).toBeNull();
});

it("renders model content as text instead of HTML", () => {
  const map = createMapResponse();
  map.nodes[1].data.summary = "<script>alert('unsafe')</script>";

  const { container } = render(<MindMapResult state={{ status: "success", request: sampleRequest, map }} />);

  fireEvent.click(screen.getByRole("button", { name: "Lista" }));

  expect(screen.getByText("<script>alert('unsafe')</script>")).toBeTruthy();
  expect(container.querySelector("script")).toBeNull();
});

it("announces loading and removes the previous list", () => {
  const { rerender } = render(<MindMapResult state={{ status: "success", request: sampleRequest, map: createMapResponse() }} />);

  rerender(<MindMapResult state={{ status: "generating", request: sampleRequest }} />);

  expect(screen.getByRole("status").textContent).toContain("Gerando conceitos");
  expect(screen.queryByRole("list")).toBeNull();
  expect(screen.queryByTestId("map-canvas")).toBeNull();
});

it("switches views without unmounting the canvas and exposes all relationships in the list", () => {
  render(<MindMapResult state={{ status: "success", request: sampleRequest, map: createMapResponse() }} />);

  const canvas = screen.getByTestId("map-canvas");

  expect(screen.queryByRole("region", { name: "Leitura textual do mapa" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Lista" }));
  expect(canvas.closest("[hidden]")).not.toBeNull();
  expect(screen.getByRole("list", { name: "Relações entre conceitos" }).textContent).toContain("Fotossíntese utiliza Clorofila");
  fireEvent.click(screen.getByRole("button", { name: "Mapa" }));
  expect(screen.getByTestId("map-canvas")).toBe(canvas);
  expect(canvas.closest("[hidden]")).toBeNull();
});

it("offers a focused textual fallback when the canvas requests recovery", async () => {
  render(<MindMapResult state={{ status: "success", request: sampleRequest, map: createMapResponse() }} />);

  fireEvent.click(screen.getByRole("button", { name: "Simular falha do canvas" }));

  const panel = screen.getByRole("region", { name: "Leitura textual do mapa" });

  await waitFor(() => expect(document.activeElement).toBe(panel));
});
