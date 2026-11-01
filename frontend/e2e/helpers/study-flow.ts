import { expect, type Page } from "@playwright/test";
import { createMapResponse } from "../../features/mind-map/test-fixtures";

export async function mockStudyApi(page: Page, response = createMapResponse()) {
  await page.route("**/api/**", async (route) => {
    const headers = {
      "access-control-allow-origin": "*",
      "access-control-allow-headers": "content-type",
      "access-control-allow-methods": "POST, OPTIONS",
    };

    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
    } else if (new URL(route.request().url()).pathname === "/api/documents/ingest") {
      await route.fulfill({ status: 201, headers, json: { document_name: "biologia.pdf", total_chunks: 2, message: "Ingested." } });
    } else {
      await route.fulfill({ headers, json: response });
    }
  });
}

export async function prepareMap(page: Page, response = createMapResponse()) {
  await mockStudyApi(page, response);
  await page.goto("/");
  await page.getByLabel("Arquivo PDF").setInputFiles({ name: "biologia.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF test") });
  await page.getByRole("button", { name: "Enviar PDF" }).click();
  await page.getByLabel("O que você quer estudar?").fill("Como funciona a fotossíntese?");
  await page.getByRole("button", { name: "Gerar mapa", exact: true }).click();

  const canvas = page.getByRole("region", { name: "Mapa mental interativo" });

  await expect(canvas.locator(".react-flow__node")).toHaveCount(response.nodes.length);
  await expect(canvas.locator(".react-flow__edge")).toHaveCount(response.edges.length);

  return canvas;
}
