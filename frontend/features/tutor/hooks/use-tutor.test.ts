import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DOCUMENT_ID } from "@/features/mind-map/test-fixtures";
import { ApiError } from "@/services/http-client";
import { askTutor } from "../services/ask-tutor";
import { createAnswer } from "../test-fixtures";
import type { AskResponse } from "../types";
import { historyFrom, useTutor } from "./use-tutor";

vi.mock("../services/ask-tutor", () => ({ askTutor: vi.fn() }));

const ask = vi.mocked(askTutor);
const OTHER_DOCUMENT = "1c9a4d7e-2b3f-4a5c-8d6e-7f8091a2b3c4";

beforeEach(() => { ask.mockReset(); });
afterEach(cleanup);

describe("useTutor", () => {
  it("sends the last exchanges as history and the selected concept", async () => {
    ask.mockResolvedValueOnce(createAnswer({ answer: "Primeira resposta." })).mockResolvedValueOnce(createAnswer());
    const { result } = renderHook(() => useTutor(DOCUMENT_ID));

    await act(() => result.current.ask("O que é a clorofila?"));
    act(() => result.current.setConcept({ nodeId: "light-phase", label: "Fase clara" }));
    await act(() => result.current.ask("E onde ela acontece?"));

    expect(ask.mock.calls[1][1]).toEqual({
      question: "E onde ela acontece?",
      history: [
        { role: "student", content: "O que é a clorofila?" },
        { role: "tutor", content: "Primeira resposta." },
      ],
      node_id: "light-phase",
    });
    expect(result.current.exchanges.map((exchange) => exchange.status)).toEqual(["answered", "answered"]);
    expect(result.current.exchanges[1].concept).toEqual({ nodeId: "light-phase", label: "Fase clara" });
  });

  it("keeps at most the last 4 exchanges in the history", () => {
    const exchanges = Array.from({ length: 6 }, (_, index) => ({
      id: index, question: `Pergunta ${index}`, status: "answered" as const, response: createAnswer({ answer: `Resposta ${index}` }),
    }));

    const history = historyFrom(exchanges);

    expect(history).toHaveLength(8);
    expect(history[0]).toEqual({ role: "student", content: "Pergunta 2" });
  });

  it("shows validation errors without calling the API", async () => {
    const { result } = renderHook(() => useTutor(DOCUMENT_ID));

    await act(() => result.current.ask("oi"));

    expect(ask).not.toHaveBeenCalled();
    expect(result.current.validationError?.message).toBe("Escreva a dúvida com pelo menos 3 caracteres.");
    expect(result.current.exchanges).toEqual([]);
  });

  it("records API errors in the conversation", async () => {
    ask.mockImplementation(() => Promise.reject(
      new ApiError("http", "O tutor está indisponível no momento. Tente novamente em instantes.", 503),
    ));
    const { result } = renderHook(() => useTutor(DOCUMENT_ID));

    await act(() => result.current.ask("O que é a clorofila?"));

    const [exchange] = result.current.exchanges;
    expect(exchange.status).toBe("error");
    expect(exchange.status === "error" && exchange.error.status).toBe(503);
    expect(historyFrom(result.current.exchanges)).toEqual([]);
  });

  it("cancels a pending question and removes it from the conversation", async () => {
    ask.mockImplementation((_, __, options) => new Promise((_, reject) => {
      options?.signal?.addEventListener("abort", () => reject(new ApiError("cancelled", "Cancelada.")));
    }));
    const { result } = renderHook(() => useTutor(DOCUMENT_ID));

    let pending!: Promise<boolean>;
    act(() => { pending = result.current.ask("O que é a clorofila?"); });
    expect(result.current.isAsking).toBe(true);

    await act(async () => { result.current.cancel(); await pending; });

    expect(result.current.exchanges).toEqual([]);
    expect(result.current.isAsking).toBe(false);
  });

  it("starts a new session for another material and ignores late answers", async () => {
    let resolve!: (value: AskResponse) => void;
    ask.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const { result, rerender } = renderHook(({ id }) => useTutor(id), { initialProps: { id: DOCUMENT_ID } });

    act(() => { void result.current.ask("O que é a clorofila?"); });
    act(() => result.current.setConcept({ nodeId: "chlorophyll", label: "Clorofila" }));
    rerender({ id: OTHER_DOCUMENT });

    expect(result.current.exchanges).toEqual([]);
    expect(result.current.concept).toBeNull();

    await act(async () => { resolve(createAnswer()); });
    expect(result.current.exchanges).toEqual([]);
  });
});
