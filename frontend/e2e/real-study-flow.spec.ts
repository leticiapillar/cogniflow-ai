import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { assertLocalApi, readProposalPdf, removeTestDocument } from "../test-utils/real-api";
import { generateMapResponseSchema } from "../features/mind-map/schemas";

test("completes the real PDF to map to textual reading flow", async ({ page }, testInfo) => {
  test.skip(!process.env.COGNIFLOW_INTEGRATION_URL, "Requer FastAPI e pgvector locais.");
  assertLocalApi(process.env.COGNIFLOW_INTEGRATION_URL!);

  const name = `cogniflow-stage5-${randomUUID()}.pdf`;
  const bytes = await readProposalPdf();

  try {
    await page.goto("/");
    await page.getByLabel("Arquivo PDF").setInputFiles({ name, mimeType: "application/pdf", buffer: bytes });
    await page.getByRole("button", { name: "Enviar PDF" }).click();

    const query = page.getByLabel("O que você quer estudar?");

    await expect(query).toBeFocused();

    await query.fill("Arquitetura técnica CogniFlow AI FastAPI pgvector RAG");

    const responsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" && new URL(response.url()).pathname === "/api/generate-map");

    await page.getByRole("button", { name: "Gerar mapa", exact: true }).click();

    const response = await responsePromise;

    expect(response.status()).toBe(200);

    const map = generateMapResponseSchema.parse(await response.json());

    expect(map.source_chunks_used).toBeGreaterThan(0);

    const canvas = page.getByRole("region", { name: "Mapa mental interativo" });

    await expect(canvas.locator(".react-flow__node")).toHaveCount(map.nodes.length);
    await expect(canvas.locator(".react-flow__edge")).toHaveCount(map.edges.length);

    await page.getByRole("button", { name: "Reorganizar mapa" }).click();
    await page.getByRole("button", { name: "Lista", exact: true }).click();

    await expect(page.getByRole("list", { name: "Conceitos gerados" }).locator(":scope > li")).toHaveCount(map.nodes.length);
    await expect(page.getByRole("list", { name: "Relações entre conceitos" }).locator(":scope > li")).toHaveCount(map.edges.length);
    await page.screenshot({ path: testInfo.outputPath("fluxo-real.png"), fullPage: true });
  } finally {
    await removeTestDocument(name);
  }
});
