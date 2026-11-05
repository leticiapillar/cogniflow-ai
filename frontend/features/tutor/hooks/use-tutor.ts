import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/services/http-client";
import { MAX_HISTORY_TURNS, askRequestSchema } from "../schemas";
import { askTutor } from "../services/ask-tutor";
import type { ChatTurn, ConceptContext, TutorExchange } from "../types";

type Session = {
  documentId: string | null;
  exchanges: TutorExchange[];
  concept: ConceptContext | null;
  validationError: ApiError | null;
};

const emptySession = (documentId: string | null): Session => ({
  documentId, exchanges: [], concept: null, validationError: null,
});

/** History sent to the API: the last answered exchanges (question and direct answer). */
export function historyFrom(exchanges: TutorExchange[]): ChatTurn[] {
  const turns = exchanges.flatMap((exchange): ChatTurn[] => exchange.status === "answered"
    ? [
      { role: "student", content: exchange.question },
      { role: "tutor", content: exchange.response.answer.slice(0, 2000) },
    ]
    : []);
  return turns.slice(-MAX_HISTORY_TURNS);
}

/** Question-and-answer session about one document. Resets when the document changes. */
export function useTutor(documentId: string | null) {
  const [stored, setStored] = useState<Session>(() => emptySession(documentId));
  const session = stored.documentId === documentId ? stored : emptySession(documentId);
  const activeRequest = useRef<AbortController | null>(null);
  const currentDocument = useRef(documentId);
  const nextId = useRef(1);

  useEffect(() => {
    currentDocument.current = documentId;
    return () => {
      activeRequest.current?.abort();
      activeRequest.current = null;
    };
  }, [documentId]);

  const update = useCallback((change: (current: Session) => Session) => {
    // A late answer about a previous material must not touch the current session.
    if (currentDocument.current !== documentId) return;
    setStored((current) => change(current.documentId === documentId ? current : emptySession(documentId)));
  }, [documentId]);

  const setConcept = useCallback((concept: ConceptContext | null) => {
    update((current) => ({ ...current, concept }));
  }, [update]);

  const ask = useCallback(async (question: string): Promise<boolean> => {
    if (!documentId || activeRequest.current) return false;

    const request = askRequestSchema.safeParse({
      question,
      history: historyFrom(session.exchanges),
      node_id: session.concept?.nodeId ?? null,
    });
    if (!request.success) {
      update((current) => ({ ...current, validationError: new ApiError("validation", request.error.issues[0].message) }));
      return false;
    }

    const id = nextId.current++;
    const concept = session.concept ?? undefined;
    const controller = new AbortController();
    activeRequest.current = controller;

    update((current) => ({
      ...current,
      validationError: null,
      exchanges: [...current.exchanges, { id, question: request.data.question, concept, status: "pending" }],
    }));

    const settle = (exchange: TutorExchange) => update((current) => ({
      ...current,
      exchanges: current.exchanges.map((item) => (item.id === id ? exchange : item)),
    }));

    try {
      const response = await askTutor(documentId, request.data, { signal: controller.signal });
      if (controller.signal.aborted) return true;
      settle({ id, question: request.data.question, concept, status: "answered", response });
    } catch (error) {
      const apiError = error instanceof ApiError
        ? error
        : new ApiError("network", "Não foi possível falar com o tutor. Tente novamente.");
      if (apiError.kind === "cancelled") {
        update((current) => ({ ...current, exchanges: current.exchanges.filter((item) => item.id !== id) }));
      } else {
        settle({ id, question: request.data.question, concept, status: "error", error: apiError });
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
    }
    return true;
  }, [documentId, session.concept, session.exchanges, update]);

  const cancel = useCallback(() => {
    activeRequest.current?.abort();
  }, []);

  return {
    exchanges: session.exchanges,
    concept: session.concept,
    validationError: session.validationError,
    isAsking: session.exchanges.some((exchange) => exchange.status === "pending"),
    ask,
    cancel,
    setConcept,
  };
}
