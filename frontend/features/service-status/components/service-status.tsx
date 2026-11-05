import type { ServiceHealthState } from "../hooks/use-service-health";

/** Shown only while the AI service is not ready; the upload stays disabled meanwhile. */
export function ServiceStatus({ state, onRecheck }: { state: ServiceHealthState; onRecheck: () => void }) {
  if (state.status === "ready") return null;

  return (
    <section aria-labelledby="service-status-heading"
      className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-sm leading-relaxed">
      <h2 id="service-status-heading" className="font-semibold text-amber-900">Serviço de IA</h2>
      <p role="status" aria-atomic="true" className="mt-1 text-amber-900">
        {state.status === "checking"
          ? "Verificando o serviço de IA…"
          : state.reason === "unreachable"
            ? "Não foi possível conectar ao serviço. Confira se o backend está ativo."
            : "O serviço de IA está iniciando ou indisponível."}
      </p>
      {state.status === "unavailable" && (
        <>
          <p className="mt-1 text-amber-900">O envio de PDF fica disponível quando o serviço estiver pronto.</p>
          <button type="button" onClick={onRecheck}
            className="mt-3 rounded-lg border border-amber-400 bg-surface px-4 py-2 font-semibold">
            Verificar novamente
          </button>
        </>
      )}
    </section>
  );
}
