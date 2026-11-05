import { expect, type Page } from "@playwright/test";
import { createStatusResponse, DOCUMENT_ID } from "../../features/mind-map/test-fixtures";
import type { MindMapStatusResponse } from "../../features/mind-map/types";
import { createAnswer } from "../../features/tutor/test-fixtures";
import type { AskResponse } from "../../features/tutor/types";

const headers = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "content-type",
  "access-control-allow-methods": "GET, POST, OPTIONS",
};

export type MockApiOptions = {
  /** Successive answers of GET /mind-map; the last one repeats. */
  statuses?: MindMapStatusResponse[];
  /** Answer of POST /regenerate and /retry, followed by `afterRetry` on the next polls. */
  afterRetry?: MindMapStatusResponse[];
  healthy?: boolean;
  answer?: AskResponse | { status: number };
};

export type MockApi = { askBodies: unknown[]; setHealthy: (healthy: boolean) => void };

export async function mockStudyApi(page: Page, options: MockApiOptions = {}): Promise<MockApi> {
  let statuses = [...(options.statuses ?? [createStatusResponse()])];
  let healthy = options.healthy ?? true;
  const askBodies: unknown[] = [];

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
    } else if (path === "/api/health") {
      await route.fulfill({ headers, json: {
        status: healthy ? "healthy" : "degraded", database_connected: true, ollama_connected: healthy,
        issues: healthy ? [] : ["Ollama server is unreachable"],
      } });
    } else if (path === "/api/documents/ingest") {
      await route.fulfill({ status: 201, headers, json: {
        document_id: DOCUMENT_ID, document_name: "biologia.pdf", page_count: 3, total_chunks: 2, message: "Ingested.",
      } });
    } else if (path.endsWith("/mind-map")) {
      const next = statuses.length > 1 ? statuses.shift()! : statuses[0];
      await route.fulfill({ headers, json: next });
    } else if (path.endsWith("/regenerate") || path.endsWith("/retry")) {
      statuses = [...(options.afterRetry ?? [createStatusResponse()])];
      await route.fulfill({ status: 202, headers, json: { ...statuses[0], status: "processing", mind_map: null,
        progress: { phase: "mapping", done: 0, total: 1, current_section: null, message: "Lendo a seção 1 de 1." } } });
    } else if (path.endsWith("/ask")) {
      askBodies.push(request.postDataJSON());
      const answer = options.answer ?? createAnswer();
      if ("status" in answer) await route.fulfill({ status: answer.status, headers, json: { detail: "private detail" } });
      else await route.fulfill({ headers, json: answer });
    } else {
      await route.fulfill({ status: 404, headers, json: { detail: "not mocked" } });
    }
  });

  return { askBodies, setHealthy: (value) => { healthy = value; } };
}

export async function uploadPdf(page: Page) {
  await page.getByLabel("Arquivo PDF").setInputFiles({ name: "biologia.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF test") });
  await page.getByRole("button", { name: "Enviar PDF" }).click();
}

/** Opens the app, sends a PDF and waits for the map: theme and axes, all closed. */
export async function prepareMap(page: Page, options: MockApiOptions = {}) {
  const api = await mockStudyApi(page, options);
  await page.goto("/");
  await uploadPdf(page);

  const canvas = page.getByRole("region", { name: "Mapa mental interativo" });
  const map = (options.statuses?.at(-1) ?? createStatusResponse()).mind_map!;
  const closedNodes = map.nodes.filter((node) => ["root", "topic"].includes(node.data.category));

  await expect(canvas.locator(".react-flow__node")).toHaveCount(closedNodes.length);
  await expect(canvas.locator(".react-flow__edge")).toHaveCount(closedNodes.length - 1);

  return { canvas, api };
}
