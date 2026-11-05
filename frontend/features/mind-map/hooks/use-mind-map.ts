import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/services/http-client";
import { getMindMapStatus, regenerateMindMap, retryMindMapSection } from "../services/mind-map-api";
import type { MindMapState, MindMapStatusResponse } from "../types";

export const POLL_INTERVAL_MS = 2_000;

type Load = (signal: AbortSignal) => Promise<MindMapStatusResponse>;

function toState(response: MindMapStatusResponse): MindMapState {
  if (response.status === "pending" || response.status === "processing") return { status: "generating", response };
  if (response.status === "failed") return { status: "failed", response };
  return { status: "ready", response, map: response.mind_map! };
}

/** Follows the background generation of a document's mind map by polling its status. */
export function useMindMap(documentId: string | null) {
  // The state is stored with the document it belongs to, so a document change
  // immediately reads as "loading" without setting state inside an effect.
  const [entry, setEntry] = useState<{ documentId: string | null; state: MindMapState }>({
    documentId: null,
    state: { status: "idle" },
  });
  const version = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(() => {
    version.current += 1;
    controller.current?.abort();
    controller.current = null;
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const follow = useCallback((id: string, first: Load) => {
    stop();
    const current = version.current;
    const poll: Load = (signal) => getMindMapStatus(id, { signal });

    const run = async (load: Load) => {
      const abort = new AbortController();
      controller.current = abort;

      try {
        const response = await load(abort.signal);
        if (version.current !== current) return;

        const next = toState(response);
        setEntry({ documentId: id, state: next });
        if (next.status === "generating") timer.current = setTimeout(() => void run(poll), POLL_INTERVAL_MS);
      } catch (error) {
        if (version.current !== current) return;

        const apiError = error instanceof ApiError
          ? error
          : new ApiError("network", "Não foi possível consultar o mapa. Tente novamente.");

        if (apiError.kind === "cancelled") return;
        if (apiError.status === 409) {
          // A generation is already running: keep following it.
          timer.current = setTimeout(() => void run(poll), POLL_INTERVAL_MS);
          return;
        }
        setEntry({
          documentId: id,
          state: apiError.status === 404 ? { status: "missing" } : { status: "error", error: apiError },
        });
      } finally {
        if (controller.current === abort) controller.current = null;
      }
    };

    void run(first);
  }, [stop]);

  useEffect(() => {
    if (!documentId) return stop;
    follow(documentId, (signal) => getMindMapStatus(documentId, { signal }));
    return stop;
  }, [documentId, follow, stop]);

  const restart = useCallback((load: (id: string, signal: AbortSignal) => Promise<MindMapStatusResponse>) => {
    if (!documentId) return;
    setEntry({ documentId, state: { status: "loading" } });
    follow(documentId, (signal) => load(documentId, signal));
  }, [documentId, follow]);

  const refresh = useCallback(() => restart((id, signal) => getMindMapStatus(id, { signal })), [restart]);
  const regenerate = useCallback(() => restart((id, signal) => regenerateMindMap(id, { signal })), [restart]);
  const retrySection = useCallback(
    (sectionIndex: number) => restart((id, signal) => retryMindMapSection(id, sectionIndex, { signal })),
    [restart],
  );

  const state: MindMapState = !documentId
    ? { status: "idle" }
    : entry.documentId === documentId ? entry.state : { status: "loading" };

  return { state, refresh, regenerate, retrySection };
}
