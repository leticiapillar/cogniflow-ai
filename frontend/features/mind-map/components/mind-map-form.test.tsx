import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ApiError } from "@/services/http-client";
import { sampleRequest } from "../test-fixtures";
import { MindMapForm } from "./mind-map-form";

afterEach(cleanup);

const props = () => ({ query: "", state: { status: "idle" as const }, onQueryChange: vi.fn(), onGenerate: vi.fn(), onCancel: vi.fn() });

it("keeps the query disabled until a document is ready", () => {
  const handlers = props();

  render(<MindMapForm {...handlers} />);

  expect(screen.getByLabelText("O que você quer estudar?").closest("fieldset")?.disabled).toBe(true);
  expect(screen.getByText("Envie um PDF para habilitar a consulta.")).toBeTruthy();
});

it("enables the selected document form and forwards editing and submission", () => {
  const handlers = props();

  render(<MindMapForm {...handlers} documentName="biologia.pdf" />);

  expect(screen.getByLabelText("O que você quer estudar?").closest("fieldset")?.disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("O que você quer estudar?"), { target: { value: sampleRequest.query } });

  expect(handlers.onQueryChange).toHaveBeenCalledWith(sampleRequest.query);
  fireEvent.submit(screen.getByRole("form", { name: "Geração de mapa mental" }));

  expect(handlers.onGenerate).toHaveBeenCalledTimes(1);
});

it("blocks duplicate submission while generating and provides cancellation", () => {
  const handlers = props();

  render(<MindMapForm {...handlers} documentName="biologia.pdf" state={{ status: "generating", request: sampleRequest }} />);

  expect((screen.getByRole("button", { name: "Gerando mapa…" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Cancelar geração" }));

  expect(handlers.onCancel).toHaveBeenCalledTimes(1);
  expect((screen.getByLabelText("O que você quer estudar?") as HTMLTextAreaElement).disabled).toBe(false);
});

it("associates validation errors with the query and offers retry", () => {
  render(<MindMapForm {...props()} documentName="biologia.pdf" query="ab"
    state={{ status: "error", error: new ApiError("validation", "Escreva pelo menos 3 caracteres.") }} />);

  const input = screen.getByLabelText("O que você quer estudar?");

  expect(input.getAttribute("aria-invalid")).toBe("true");
  expect(input.getAttribute("aria-describedby")).toContain("query-error");
  expect(screen.getByRole("alert").textContent).toContain("3 caracteres");
  expect(screen.getByRole("button", { name: "Tentar novamente" })).toBeTruthy();
});
