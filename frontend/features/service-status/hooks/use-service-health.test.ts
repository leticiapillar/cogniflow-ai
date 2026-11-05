import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "@/services/http-client";
import { getServiceHealth, type HealthResponse } from "../services/get-service-health";
import { useServiceHealth } from "./use-service-health";

vi.mock("../services/get-service-health", () => ({ getServiceHealth: vi.fn() }));

const health = vi.mocked(getServiceHealth);
const response = (status: HealthResponse["status"]): HealthResponse => ({
  status, database_connected: true, ollama_connected: status === "healthy", issues: [],
});

beforeEach(() => { health.mockReset(); });
afterEach(cleanup);

it("is ready when the backend reports healthy", async () => {
  health.mockResolvedValue(response("healthy"));
  const { result } = renderHook(() => useServiceHealth());

  expect(result.current.state).toEqual({ status: "checking" });
  await act(async () => {});
  expect(result.current.state).toEqual({ status: "ready" });
});

it("distinguishes a degraded service from an unreachable backend and checks again on demand", async () => {
  health
    .mockResolvedValueOnce(response("degraded"))
    .mockImplementationOnce(() => Promise.reject(new ApiError("network", "Sem conexão.")))
    .mockResolvedValueOnce(response("healthy"));
  const { result } = renderHook(() => useServiceHealth());

  await act(async () => {});
  expect(result.current.state).toEqual({ status: "unavailable", reason: "degraded" });

  await act(async () => { result.current.recheck(); });
  expect(result.current.state).toEqual({ status: "unavailable", reason: "unreachable" });

  await act(async () => { result.current.recheck(); });
  expect(result.current.state).toEqual({ status: "ready" });
});
