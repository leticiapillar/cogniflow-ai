import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { createMapResponse } from "../test-fixtures";
import { MindMapOutline } from "./mind-map-outline";

afterEach(cleanup);

it("presents all concepts, summaries and directed relationships as text", () => {
  render(<MindMapOutline map={createMapResponse()} />);

  expect(screen.getByRole("list", { name: "Conceitos gerados" }).children).toHaveLength(2);
  expect(screen.getByRole("list", { name: "Relações entre conceitos" }).textContent).toBe("Fotossíntese utiliza Clorofila.");
  expect(screen.getByText("Pigmento que absorve luz.")).toBeTruthy();
});

it("explains absent summaries and relationships without requiring the canvas", () => {
  const map = createMapResponse();
  map.nodes = [map.nodes[0]];
  map.nodes[0].data.summary = null;
  map.edges = [];

  render(<MindMapOutline map={map} />);

  expect(screen.getByText("Resumo não informado.")).toBeTruthy();
  expect(screen.getByText("Não foram retornadas relações entre os conceitos.")).toBeTruthy();
});
