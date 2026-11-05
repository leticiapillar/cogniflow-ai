import { z } from "zod";
import { ApiError, requestJson } from "@/services/http-client";

export const healthResponseSchema = z.object({
  status: z.enum(["healthy", "degraded"]),
  database_connected: z.boolean(),
  ollama_connected: z.boolean(),
  issues: z.array(z.string()),
});

export type HealthResponse = z.infer<typeof healthResponseSchema>;

// The first check loads the embedding model in Ollama, which can take a while.
const HEALTH_TIMEOUT_MS = 90_000;

export async function getServiceHealth(options: { signal?: AbortSignal } = {}): Promise<HealthResponse> {
  const response = await requestJson("/api/health", { timeoutMs: HEALTH_TIMEOUT_MS, ...options });
  const health = healthResponseSchema.safeParse(response);

  if (!health.success) {
    throw new ApiError("invalid-response", "O serviço retornou um estado inválido. Tente novamente.");
  }
  return health.data;
}
