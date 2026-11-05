import { useCallback, useEffect, useRef, useState } from "react";
import { getServiceHealth } from "../services/get-service-health";

export type ServiceHealthState =
  | { status: "checking" }
  | { status: "ready" }
  | { status: "unavailable"; reason: "degraded" | "unreachable" };

/** Checks GET /api/health on load and on demand ("Verificar novamente"). */
export function useServiceHealth() {
  const [state, setState] = useState<ServiceHealthState>({ status: "checking" });
  const cancelCurrent = useRef<(() => void) | null>(null);

  // State changes only in the promise callbacks, never synchronously in an effect.
  const check = useCallback(() => {
    cancelCurrent.current?.();
    const abort = new AbortController();
    cancelCurrent.current = () => abort.abort();

    getServiceHealth({ signal: abort.signal }).then(
      (health) => {
        if (abort.signal.aborted) return;
        setState(health.status === "healthy" ? { status: "ready" } : { status: "unavailable", reason: "degraded" });
      },
      () => {
        if (abort.signal.aborted) return;
        setState({ status: "unavailable", reason: "unreachable" });
      },
    );
  }, []);

  useEffect(() => {
    check();
    return () => {
      cancelCurrent.current?.();
      cancelCurrent.current = null;
    };
  }, [check]);

  const recheck = useCallback(() => {
    setState({ status: "checking" });
    check();
  }, [check]);

  return { state, recheck };
}
