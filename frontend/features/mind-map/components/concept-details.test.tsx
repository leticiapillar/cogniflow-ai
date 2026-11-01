import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { createMapResponse } from "../test-fixtures";
import { ConceptDetails } from "./concept-details";

afterEach(cleanup);

it("shows complete summaries and original relationship labels for the selected concept", () => {
  const map = createMapResponse();
  map.nodes[0].data.label = "Um título completo que deve permanecer acessível no painel de detalhes";

  render(<ConceptDetails node={map.nodes[0]} map={map} />);

  expect(screen.getByText(map.nodes[0].data.label)).toBeTruthy();
  expect(screen.getByText(map.nodes[0].data.summary!)).toBeTruthy();
  expect(screen.getByRole("list", { name: "Relações do conceito" }).textContent).toContain("utiliza → Clorofila");
});

it("provides selection instructions when no concept is selected", () => {
  render(<ConceptDetails map={createMapResponse()} />);

  expect(screen.getByText(/Selecione um conceito no mapa/)).toBeTruthy();
});
