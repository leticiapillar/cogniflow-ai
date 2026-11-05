import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useTopicExpansion } from "../expansion";
import { createMapResponse } from "../test-fixtures";
import type { MindMap, MindMapNode } from "../types";
import { MindMapOutline } from "./mind-map-outline";

afterEach(cleanup);

function Outline({ map, onAskAbout }: { map: MindMap; onAskAbout?: (node: MindMapNode) => void }) {
  const expansion = useTopicExpansion(map);
  return <MindMapOutline map={map} expansion={expansion} onAskAbout={onAskAbout} />;
}

it("starts with the central theme and the numbered axes in study order, all closed", () => {
  const map = createMapResponse();
  map.nodes.reverse(); // the API order must not change the study order

  render(<Outline map={map} />);

  expect(screen.getByText("Conversão de energia luminosa.")).toBeTruthy();
  const axes = within(screen.getByRole("list", { name: "Eixos de estudo" })).getAllByRole("heading", { level: 4 });
  expect(axes.map((axis) => axis.textContent)).toEqual(["Estruturas da planta", "Etapas do processo"]);
  expect(screen.getByRole("button", { name: /Abrir eixo 1 \(1 conceito\)/ }).getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByText("Clorofila")).toBeNull();
});

it("opens an axis to show its concepts with relation, acronyms and examples", () => {
  render(<Outline map={createMapResponse()} />);

  fireEvent.click(screen.getByRole("button", { name: /Abrir eixo 2/ }));

  const concepts = screen.getByRole("list", { name: "Conceitos do eixo 2" });
  expect(within(concepts).getByText("Fase clara")).toBeTruthy();
  expect(within(concepts).getByText("Etapas do processo depende de Fase clara.")).toBeTruthy();
  expect(within(concepts).getByRole("definition").textContent).toBe("Adenosina trifosfato");
  expect(screen.queryByText("Clorofila")).toBeNull();

  fireEvent.click(screen.getByRole("button", { name: /Abrir eixo 1/ }));
  expect(screen.getByRole("list", { name: "Exemplos de Clorofila" }).textContent).toContain("Exemplo: Folha verde.");

  fireEvent.click(screen.getByRole("button", { name: "Fechar eixo 2" }));
  expect(screen.queryByText("Fase clara")).toBeNull();
});

it("offers to ask the tutor about a concept", () => {
  const onAskAbout = vi.fn();
  render(<Outline map={createMapResponse()} onAskAbout={onAskAbout} />);

  fireEvent.click(screen.getByRole("button", { name: /Abrir eixo 1/ }));
  fireEvent.click(screen.getByRole("button", { name: "Tirar dúvida sobre Clorofila" }));

  expect(onAskAbout).toHaveBeenCalledWith(expect.objectContaining({ id: "chlorophyll" }));
});

it("explains absent summaries", () => {
  const map = createMapResponse();
  map.nodes[0].data.summary = null;

  render(<Outline map={map} />);

  expect(screen.getByText("Resumo não informado.")).toBeTruthy();
});
