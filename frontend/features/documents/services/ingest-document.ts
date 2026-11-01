import { ApiError, requestJson } from "@/services/http-client";
import { documentUploadResponseSchema, pdfFileSchema } from "../schemas";
import type { DocumentUploadResponse } from "../types";

export async function ingestDocument(
  file: File,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<DocumentUploadResponse> {
  const validatedFile = pdfFileSchema.safeParse(file);

  if (!validatedFile.success) {
    throw new ApiError("validation", validatedFile.error.issues[0].message);
  }

  const body = new FormData();

  body.append("file", validatedFile.data);

  let response: unknown;

  try {
    response = await requestJson("/api/documents/ingest", { method: "POST", body, ...options });
  } catch (error) {
    if (error instanceof ApiError && error.kind === "http") {
      if (error.status === 400) {
        throw new ApiError("http", "O conteúdo do PDF foi rejeitado. Selecione outro material.", 400);
      }
      if (error.status === 422) {
        throw new ApiError("http", "Não foi possível ler esse PDF. Confira se ele contém texto selecionável e tem até 20 MiB.", 422);
      }
    }

    throw error;
  }

  const document = documentUploadResponseSchema.safeParse(response);

  if (!document.success) {
    throw new ApiError("invalid-response", "O serviço retornou dados de documento inválidos. Tente novamente.");
  }

  if (document.data.total_chunks === 0) {
    throw new ApiError("invalid-response", "Nenhum trecho foi extraído. Selecione um PDF com texto selecionável.");
  }

  return document.data;
}
