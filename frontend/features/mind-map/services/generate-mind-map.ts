import { ApiError, requestJson } from "@/services/http-client";
import { generateMapRequestSchema, generateMapResponseSchema } from "../schemas";
import type { GenerateMapRequest, GenerateMapResponse } from "../types";

export async function generateMindMap(
  input: GenerateMapRequest,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<GenerateMapResponse> {
  const request = generateMapRequestSchema.safeParse(input);

  if (!request.success) {
    throw new ApiError("validation", request.error.issues[0].message);
  }

  let response: unknown;

  try {
    response = await requestJson("/api/generate-map", {
      ...options,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.data),
    });
  } catch (error) {
    if (error instanceof ApiError && error.kind === "http") {
      if (error.status === 422) {
        throw new ApiError("http", "A consulta não foi aceita. Revise o tema de estudo e tente novamente.", 422);
      }
      if (error.status === 502) {
        throw new ApiError("http", "Não foi possível gerar um mapa válido. Tente novamente ou reformule a consulta.", 502);
      }
    }
    throw error;
  }

  const map = generateMapResponseSchema.safeParse(response);

  if (!map.success) {
    throw new ApiError("invalid-response", "O serviço retornou um mapa com estrutura inválida. Tente novamente.");
  }

  return map.data;
}
