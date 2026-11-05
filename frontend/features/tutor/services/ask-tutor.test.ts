import { beforeEach, describe, expect, it, vi } from "vitest";
import { DOCUMENT_ID } from "@/features/mind-map/test-fixtures";
import { createAnswer } from "../test-fixtures";
import { askTutor } from "./ask-tutor";

beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000"));

describe("askTutor", () => {
  it("sends the question, the history and the concept of the map", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json(createAnswer()));
    vi.stubGlobal("fetch", fetch);

    const answer = await askTutor(DOCUMENT_ID, {
      question: "  E onde ela fica?  ",
      history: [{ role: "student", content: "O que é a clorofila?" }, { role: "tutor", content: "Um pigmento." }],
      node_id: "chlorophyll",
    });

    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe(`http://localhost:8000/api/documents/${DOCUMENT_ID}/ask`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      question: "E onde ela fica?",
      history: [{ role: "student", content: "O que é a clorofila?" }, { role: "tutor", content: "Um pigmento." }],
      node_id: "chlorophyll",
    });
    expect(answer.citations[0].page_start).toBe(2);
  });

  it("validates the question before calling the API", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    await expect(askTutor(DOCUMENT_ID, { question: "oi" })).rejects.toMatchObject({
      kind: "validation", message: "Escreva a dúvida com pelo menos 3 caracteres.",
    });
    await expect(askTutor(DOCUMENT_ID, { question: "x".repeat(1001) })).rejects.toMatchObject({ kind: "validation" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    [503, "O tutor está indisponível no momento. Tente novamente em instantes."],
    [409, "Este material foi processado com outro modelo. Envie o PDF novamente."],
    [422, "A dúvida não foi aceita. Escreva a pergunta com suas palavras, com 3 a 1.000 caracteres."],
    [404, "Este conceito não está mais no mapa. Feche a dúvida sobre o conceito e pergunte de novo."],
  ])("explains HTTP %s with a literal message", async (status, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "server internals" }, { status })));

    await expect(askTutor(DOCUMENT_ID, { question: "O que é a clorofila?" })).rejects.toMatchObject({ status, message });
  });

  it("rejects an answer outside the contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ answer: "sem estrutura" })));

    await expect(askTutor(DOCUMENT_ID, { question: "O que é a clorofila?" })).rejects.toMatchObject({ kind: "invalid-response" });
  });
});
