import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/services/http-client";
import { generateMapRequestSchema } from "../schemas";
import { generateMindMap } from "../services/generate-mind-map";
import type { GenerationState } from "../types";

export function useGenerateMindMap() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [state, setState] = useState<GenerationState>({ status: "idle" });
  const mounted = useRef(false);
  const version = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
      version.current += 1;
      activeRequest.current?.abort();
      activeRequest.current = null;
    };
  }, []);

  const reset = useCallback(() => {
    version.current += 1;
    activeRequest.current?.abort();
    activeRequest.current = null;
    setState({ status: "idle" });
  }, []);

  const updateQuery = useCallback((value: string) => {
    reset();
    setQuery(value);
  }, [reset]);

  const updateTopK = useCallback((value: number) => {
    reset();
    setTopK(value);
  }, [reset]);

  const generate = useCallback(async (documentName?: string) => {
    if (activeRequest.current) return;

    if (!documentName?.trim()) {
      setState({ status: "error", error: new ApiError("validation", "Envie um PDF antes de gerar o mapa.") });
      return;
    }
    const request = generateMapRequestSchema.safeParse({ query, document_name: documentName, top_k: topK });
    if (!request.success) {
      setState({ status: "error", error: new ApiError("validation", request.error.issues[0].message) });
      return;
    }

    const controller = new AbortController();
    const requestVersion = ++version.current;

    activeRequest.current = controller;

    setState({ status: "generating", request: request.data });

    try {
      const map = await generateMindMap(request.data, { signal: controller.signal });
      if (!mounted.current || version.current !== requestVersion) return;

      setState({ status: "success", request: request.data, map });
    } catch (error) {
      if (!mounted.current || version.current !== requestVersion) return;

      const apiError = error instanceof ApiError
        ? error
        : new ApiError("network", "Não foi possível gerar o mapa. Tente novamente.");

      setState(apiError.kind === "cancelled" ? { status: "idle" } : { status: "error", error: apiError });
    } finally {
      if (version.current === requestVersion) activeRequest.current = null;
    }
  }, [query, topK]);

  return { query, topK, state, updateQuery, updateTopK, generate, reset, cancel: reset };
}
