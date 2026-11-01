import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/services/http-client";
import { pdfFileSchema } from "../schemas";
import { ingestDocument } from "../services/ingest-document";
import type { DocumentUploadResponse, IngestionState } from "../types";

export function useIngestDocument(
  onDocumentChange: (document: DocumentUploadResponse | null) => void,
) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [state, setState] = useState<IngestionState>({ status: "idle" });
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

  const cancel = useCallback(() => {
    version.current += 1;
    activeRequest.current?.abort();
    activeRequest.current = null;

    setState({ status: "idle" });

    onDocumentChange(null);
  }, [onDocumentChange]);

  const selectFile = useCallback((file: File | null) => {
    cancel();

    setSelectedFile(file);

    if (file) {
      const result = pdfFileSchema.safeParse(file);

      if (!result.success) {
        setState({ status: "error", error: new ApiError("validation", result.error.issues[0].message) });
      }
    }
  }, [cancel]);

  const upload = useCallback(async () => {
    if (activeRequest.current) return;

    if (!selectedFile) {
      setState({ status: "error", error: new ApiError("validation", "Selecione um PDF antes de enviar.") });
      return;
    }

    const validatedFile = pdfFileSchema.safeParse(selectedFile);

    if (!validatedFile.success) {
      setState({ status: "error", error: new ApiError("validation", validatedFile.error.issues[0].message) });
      return;
    }

    const controller = new AbortController();
    const requestVersion = ++version.current;
    activeRequest.current = controller;

    onDocumentChange(null);

    setState({ status: "uploading" });

    try {
      const document = await ingestDocument(selectedFile, { signal: controller.signal });

      if (!mounted.current || version.current !== requestVersion) return;

      setState({ status: "success", document });

      onDocumentChange(document);
    } catch (error) {
      if (!mounted.current || version.current !== requestVersion) return;

      const apiError = error instanceof ApiError
        ? error
        : new ApiError("network", "Não foi possível enviar o documento. Tente novamente.");

      setState(apiError.kind === "cancelled" ? { status: "idle" } : { status: "error", error: apiError });
    } finally {
      if (version.current === requestVersion) activeRequest.current = null;
    }
  }, [selectedFile, onDocumentChange]);

  return { selectedFile, state, selectFile, upload, cancel };
}
