export type ApiErrorKind =
  | "configuration"
  | "validation"
  | "http"
  | "network"
  | "timeout"
  | "cancelled"
  | "invalid-response";

export class ApiError extends Error {
  constructor(
    public readonly kind: ApiErrorKind,
    message: string,
    public readonly status?: number,
  ) {
    super(message);

    this.name = "ApiError";
  }
}

type RequestOptions = RequestInit & { timeoutMs?: number };

function getApiUrl(path: string): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  try {
    if (!baseUrl) throw new Error("Missing API URL");

    const parsed = new URL(baseUrl);

    if (
      !["http:", "https:"].includes(parsed.protocol) ||
      parsed.username || parsed.password || parsed.search || parsed.hash
    ) {
      throw new Error("Invalid API URL");
    }

    return `${baseUrl.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
  } catch {
    throw new ApiError(
      "configuration",
      "O serviço não está configurado corretamente. Tente novamente mais tarde.",
    );
  }
}

function getHttpError(status: number): ApiError {
  const message = status === 422
    ? "Os dados enviados não foram aceitos. Revise as informações e tente novamente."
    : "Não foi possível concluir a solicitação. Tente novamente.";

  return new ApiError("http", message, status);
}

export async function requestJson(
  path: string,
  { timeoutMs = 120_000, signal, ...options }: RequestOptions = {},
): Promise<unknown> {
  const url = getApiUrl(path);

  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new ApiError("configuration", "O tempo de espera do serviço é inválido.");
  }

  if (signal?.aborted) {
    throw new ApiError("cancelled", "Solicitação cancelada.");
  }

  const controller = new AbortController();

  let timedOut = false;

  const cancel = () => controller.abort();

  signal?.addEventListener("abort", cancel, { once: true });

  const timeout = setTimeout(() => {
    if (!controller.signal.aborted) {
      timedOut = true;
      controller.abort();
    }
  }, timeoutMs);

  try {
    const headers = new Headers(options.headers);

    if (!headers.has("Accept")) headers.set("Accept", "application/json");

    const response = await fetch(url, { ...options, headers, signal: controller.signal });
  
    if (!response.ok) throw getHttpError(response.status);

    let data: unknown;
  
    try {
      data = await response.json();
    } catch (error) {
      if (controller.signal.aborted) throw error;
      throw new ApiError("invalid-response", "O serviço retornou uma resposta inválida. Tente novamente.");
    }

    if (controller.signal.aborted) throw new Error("Request aborted");

    return data;
  } catch (error) {
    if (timedOut) {
      throw new ApiError("timeout", "O serviço demorou para responder. Tente novamente.");
    }

    if (controller.signal.aborted) {
      throw new ApiError("cancelled", "Solicitação cancelada.");
    }

    if (error instanceof ApiError) throw error;

    throw new ApiError("network", "Não foi possível conectar ao serviço. Verifique sua conexão e tente novamente.");
  } finally {
    clearTimeout(timeout);

    signal?.removeEventListener("abort", cancel);
  }
}
