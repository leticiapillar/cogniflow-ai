import { ApiError, requestJson } from "@/services/http-client";
import { mindMapStatusSchema } from "../schemas";
import type { MindMapStatusResponse } from "../types";

type RequestOptions = { signal?: AbortSignal; timeoutMs?: number };

const STATUS_TIMEOUT_MS = 30_000;

function mindMapPath(documentId: string, suffix = "") {
  return `/api/documents/${encodeURIComponent(documentId)}/mind-map${suffix}`;
}

function parseStatus(response: unknown): MindMapStatusResponse {
  const status = mindMapStatusSchema.safeParse(response);

  if (!status.success) {
    throw new ApiError("invalid-response", "O serviço retornou um mapa com estrutura inválida. Tente novamente.");
  }
  return status.data;
}

function translateError(error: unknown): never {
  if (error instanceof ApiError && error.kind === "http") {
    if (error.status === 404) {
      throw new ApiError("http", "Este material ainda não tem um mapa mental.", 404);
    }
    if (error.status === 409) {
      throw new ApiError("http", "Já existe uma geração em andamento para este material.", 409);
    }
  }
  throw error;
}

export async function getMindMapStatus(
  documentId: string,
  options: RequestOptions = {},
): Promise<MindMapStatusResponse> {
  try {
    return parseStatus(await requestJson(mindMapPath(documentId), { timeoutMs: STATUS_TIMEOUT_MS, ...options }));
  } catch (error) {
    translateError(error);
  }
}

export async function regenerateMindMap(
  documentId: string,
  options: RequestOptions = {},
): Promise<MindMapStatusResponse> {
  try {
    return parseStatus(await requestJson(mindMapPath(documentId, "/regenerate"), {
      method: "POST", timeoutMs: STATUS_TIMEOUT_MS, ...options,
    }));
  } catch (error) {
    translateError(error);
  }
}

export async function retryMindMapSection(
  documentId: string,
  sectionIndex: number,
  options: RequestOptions = {},
): Promise<MindMapStatusResponse> {
  try {
    return parseStatus(await requestJson(mindMapPath(documentId, `/sections/${sectionIndex}/retry`), {
      method: "POST", timeoutMs: STATUS_TIMEOUT_MS, ...options,
    }));
  } catch (error) {
    translateError(error);
  }
}
