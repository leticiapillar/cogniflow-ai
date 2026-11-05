import { ApiError, requestJson } from "@/services/http-client";
import { askRequestSchema, askResponseSchema } from "../schemas";
import type { AskRequest, AskResponse } from "../types";

const ERROR_MESSAGES: Record<number, string> = {
  404: "Este conceito não está mais no mapa. Feche a dúvida sobre o conceito e pergunte de novo.",
  409: "Este material foi processado com outro modelo. Envie o PDF novamente.",
  422: "A dúvida não foi aceita. Escreva a pergunta com suas palavras, com 3 a 1.000 caracteres.",
  503: "O tutor está indisponível no momento. Tente novamente em instantes.",
};

export async function askTutor(
  documentId: string,
  input: AskRequest,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<AskResponse> {
  const request = askRequestSchema.safeParse(input);

  if (!request.success) {
    throw new ApiError("validation", request.error.issues[0].message);
  }

  let response: unknown;

  try {
    response = await requestJson(`/api/documents/${encodeURIComponent(documentId)}/ask`, {
      ...options,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.data),
    });
  } catch (error) {
    if (error instanceof ApiError && error.kind === "http" && error.status && ERROR_MESSAGES[error.status]) {
      throw new ApiError("http", ERROR_MESSAGES[error.status], error.status);
    }
    throw error;
  }

  const answer = askResponseSchema.safeParse(response);

  if (!answer.success) {
    throw new ApiError("invalid-response", "O tutor retornou uma resposta inválida. Tente novamente.");
  }

  return answer.data;
}
