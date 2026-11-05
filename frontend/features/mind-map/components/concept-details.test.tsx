import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useTopicExpansion } from "../expansion";
import { createMapResponse } from "../test-fixtures";
import type { MindMapNode } from "../types";
import { ConceptDetails } from "./concept-details";

afterEach(cleanup);

const map = createMapResponse();
const node = (id: string) => map.nodes.find((item) => item.id === id)!;

function Details({ id, onAskAbout }: { id: string; onAskAbout?: (node: MindMapNode) => void }) {
  const expansion = useTopicExpansion(map);
  return (
    <>
      <ConceptDetails node={node(id)} map={map} expansion={expansion} onAskAbout={onAskAbout} />
      <p data-testid="open">{[...expansion.expanded].join(",")}</p>
    </>
  );
}

it("shows the complete summary, acronyms and fixed relation verbs of the selected concept", () => {
  render(<Details id="light-phase" />);

  expect(screen.getByText("Usa a luz para produzir ATP.")).toBeTruthy();
  expect(screen.getByRole("definition").textContent).toBe("Adenosina trifosfato");
  expect(screen.getByRole("list", { name: "Relações do conceito" }).textContent)
    .toBe("Etapas do processo → depende de → Fase clara");
});

it("opens and closes an axis from its details", () => {
  render(<Details id="topic-1" />);

  expect(screen.getByText("Eixo 1")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Abrir eixo (1 conceito)" }));
  expect(screen.getByTestId("open").textContent).toBe("topic-1");
  fireEvent.click(screen.getByRole("button", { name: "Fechar eixo" }));
  expect(screen.getByTestId("open").textContent).toBe("");
});

it("asks the tutor about the selected concept", () => {
  const onAskAbout = vi.fn();
  render(<Details id="chlorophyll" onAskAbout={onAskAbout} />);

  fireEvent.click(screen.getByRole("button", { name: "Tirar dúvida sobre este conceito" }));

  expect(onAskAbout).toHaveBeenCalledWith(node("chlorophyll"));
});

it("provides selection instructions when no concept is selected", () => {
  render(<ConceptDetails map={map} />);

  expect(screen.getByText(/Selecione um conceito no mapa/)).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
});
