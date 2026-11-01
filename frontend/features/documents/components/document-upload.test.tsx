import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "@/services/http-client";
import { ingestDocument } from "../services/ingest-document";
import { DocumentUpload } from "./document-upload";

vi.mock("../services/ingest-document", () => ({ ingestDocument: vi.fn() }));

const ingest = vi.mocked(ingestDocument);
const file = () => new File(["%PDF"], "sample.pdf", { type: "application/pdf" });

beforeEach(() => ingest.mockReset());
afterEach(cleanup);

it("enables upload after valid selection and announces completion", async () => {
  const response = { document_name: "canonical.pdf", total_chunks: 2, message: "Ingested." };
  ingest.mockResolvedValue(response);
  const onChange = vi.fn();

  render(<DocumentUpload onDocumentChange={onChange} />);

  expect((screen.getByRole("button", { name: "Enviar PDF" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Arquivo PDF"), { target: { files: [file()] } });
  expect((screen.getByRole("button", { name: "Enviar PDF" }) as HTMLButtonElement).disabled).toBe(false);
  await act(async () => { fireEvent.submit(screen.getByRole("form")); });
  expect(screen.getByRole("status").textContent).toContain("2 trechos disponíveis");
  expect(onChange).toHaveBeenLastCalledWith(response);
});

it("shows a validation error without submitting an invalid file", () => {
  render(<DocumentUpload onDocumentChange={vi.fn()} />);

  const input = screen.getByLabelText("Arquivo PDF");

  fireEvent.change(input, { target: { files: [new File(["text"], "notes.txt")] } });

  expect(screen.getByRole("alert").textContent).toContain(".pdf");
  expect(input.getAttribute("aria-invalid")).toBe("true");
  expect((screen.getByRole("button", { name: "Enviar PDF" }) as HTMLButtonElement).disabled).toBe(true);
  expect(ingest).not.toHaveBeenCalled();
});

it("keeps the selected file after a server error and allows retry", async () => {
  ingest.mockRejectedValueOnce(new ApiError("network", "Falha de conexão."))
    .mockResolvedValueOnce({ document_name: "sample.pdf", total_chunks: 1, message: "Ingested." });

  render(<DocumentUpload onDocumentChange={vi.fn()} />);

  fireEvent.change(screen.getByLabelText("Arquivo PDF"), { target: { files: [file()] } });
  await act(async () => { fireEvent.submit(screen.getByRole("form")); });

  expect(screen.getByRole("alert").textContent).toBe("Falha de conexão.");
  expect(screen.getByRole("button", { name: "Tentar novamente" })).toBeTruthy();
  await act(async () => { fireEvent.submit(screen.getByRole("form")); });

  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByRole("status").textContent).toContain("1 trecho disponível");
});
