import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { createMapResponse } from "../features/mind-map/test-fixtures";
import { mockStudyApi, prepareMap } from "./helpers/study-flow";

async function audit(page: Page) {
  const result = await new AxeBuilder({ page }).include("header").include("main")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();

  expect(result.violations).toEqual([]);
}

test("has no automatically detected accessibility violations in the initial, map and list views", async ({ page }) => {
  await page.goto("/");

  await audit(page);

  const canvas = await prepareMap(page);

  await audit(page);
  await page.getByRole("button", { name: "Lista", exact: true }).click();

  await expect(canvas).toBeHidden();
  await expect(page.getByRole("list", { name: "Relações entre conceitos" })).toContainText("Fotossíntese utiliza Clorofila");
  await audit(page);
});

test("supports keyboard navigation, meaningful focus and translated graph instructions", async ({ page }) => {
  await mockStudyApi(page);
  await page.goto("/");

  await page.keyboard.press("Tab");

  await expect(page.getByRole("link", { name: "Ir para o conteúdo" })).toBeFocused();

  await page.keyboard.press("Enter");

  await expect(page.locator("#study-content")).toBeFocused();

  await page.getByLabel("Arquivo PDF").setInputFiles({ name: "biologia.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF test") });
  await page.getByLabel("Arquivo PDF").focus();
  await page.keyboard.press("Tab");

  await expect(page.getByRole("button", { name: "Enviar PDF" })).toBeFocused();

  await page.keyboard.press("Enter");

  const query = page.getByLabel("O que você quer estudar?");

  await expect(query).toBeFocused();

  await page.keyboard.type("Como funciona a fotossíntese?");
  await page.keyboard.press("Tab");

  await expect(page.getByRole("button", { name: "Gerar mapa", exact: true })).toBeFocused();

  await page.keyboard.press("Enter");

  await expect(page.getByRole("heading", { name: "Conceitos de estudo" })).toBeFocused();

  await page.keyboard.press("Tab");

  await expect(page.getByRole("button", { name: "Mapa", exact: true })).toBeFocused();

  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");

  await expect(page.getByRole("button", { name: "Lista", exact: true })).toHaveAttribute("aria-pressed", "true");

  await page.keyboard.press("Tab");

  await expect(page.getByRole("region", { name: "Leitura textual do mapa" })).toBeFocused();

  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Enter");

  const canvas = page.getByRole("region", { name: "Mapa mental interativo" });
  const node = canvas.locator('.react-flow__node[data-id="root"]');

  await node.focus();

  await expect(node).toHaveCSS("outline-style", "solid");

  await page.keyboard.press("Enter");

  await expect(page.getByRole("complementary", { name: "Detalhes do conceito" })).toContainText("Conversão de energia luminosa.");

  const before = await node.evaluate((element) => (element as HTMLElement).style.transform);

  await page.keyboard.press("ArrowDown");

  await expect.poll(() => node.evaluate((element) => (element as HTMLElement).style.transform)).not.toBe(before);
  await expect(page.getByText("Conceito movido para baixo.", { exact: true })).toBeAttached();

  const description = await node.getAttribute("aria-describedby");

  await expect(page.locator(`[id="${description}"]`)).toContainText("Pressione Enter ou Espaço");
  await expect(canvas.locator(".react-flow__edge")).toHaveAttribute("aria-label", "Relação: Fotossíntese utiliza Clorofila.");

  await page.keyboard.press("Escape");

  await expect(page.getByRole("complementary", { name: "Detalhes do conceito" })).toContainText("Selecione um conceito");
});

test("keeps manual positions, viewport and selection when switching between map and list", async ({ page }) => {
  const canvas = await prepareMap(page);
  const node = canvas.locator('.react-flow__node[data-id="root"]');

  await node.click();
  await node.focus();
  await page.keyboard.press("ArrowRight");
  await page.getByRole("button", { name: "Aumentar zoom" }).click();

  const position = await node.evaluate((element) => (element as HTMLElement).style.transform);
  const viewport = await canvas.locator(".react-flow__viewport").getAttribute("style");

  await page.getByRole("button", { name: "Lista", exact: true }).click();

  await expect(canvas).toBeHidden();

  await page.getByRole("button", { name: "Mapa", exact: true }).click();

  await expect(canvas).toBeVisible();
  await expect.poll(() => node.evaluate((element) => (element as HTMLElement).style.transform)).toBe(position);
  await expect(canvas.locator(".react-flow__viewport")).toHaveAttribute("style", viewport!);
  await expect(node).toHaveClass(/selected/);
});

test("recovers from ingestion and generation errors without losing input or keyboard access", async ({ page }) => {
  await mockStudyApi(page);
  let rejectedUpload = false;
  let rejectedGeneration = false;
  const headers = { "access-control-allow-origin": "*" };

  await page.route("**/api/documents/ingest", async (route) => {
    if (route.request().method() === "POST" && !rejectedUpload) {
      rejectedUpload = true;
      await route.fulfill({ status: 422, headers, json: { detail: "private parser details" } });
    } else await route.fallback();
  });

  await page.route("**/api/generate-map", async (route) => {
    if (route.request().method() === "POST" && !rejectedGeneration) {
      rejectedGeneration = true;
      await route.fulfill({ status: 502, headers, json: { detail: "private model details" } });
    } else await route.fallback();
  });

  await page.goto("/");
  await page.getByLabel("Arquivo PDF").setInputFiles({ name: "biologia.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF test") });
  await page.getByRole("button", { name: "Enviar PDF" }).click();

  await expect(page.getByRole("main").getByRole("alert")).toBeFocused();
  await expect(page.getByRole("main").getByRole("alert")).not.toContainText("private");
  await audit(page);
  await page.keyboard.press("Tab");

  await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeFocused();

  await page.keyboard.press("Enter");

  const query = page.getByLabel("O que você quer estudar?");

  await expect(query).toBeFocused();

  await query.fill("Como funciona a fotossíntese?");
  await page.getByRole("button", { name: "Gerar mapa", exact: true }).click();

  await expect(page.getByRole("main").getByRole("alert")).toBeFocused();
  await expect(query).toHaveValue("Como funciona a fotossíntese?");
  await audit(page);
  await page.keyboard.press("Tab");

  await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeFocused();

  await page.keyboard.press("Enter");

  await expect(page.getByRole("region", { name: "Mapa mental interativo" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
});

test("explains absent context without exposing a misleading map or list", async ({ page }) => {
  await mockStudyApi(page, { ...createMapResponse(), source_chunks_used: 0 });
  await page.goto("/");
  await page.getByLabel("Arquivo PDF").setInputFiles({ name: "biologia.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF test") });
  await page.getByRole("button", { name: "Enviar PDF" }).click();
  await page.getByLabel("O que você quer estudar?").fill("Um tema sem contexto");
  await page.getByRole("button", { name: "Gerar mapa", exact: true }).click();

  await expect(page.getByText(/Nenhum trecho do documento foi recuperado/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Mapa mental interativo" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Lista", exact: true })).toHaveCount(0);
  await audit(page);
});

test("respects reduced motion and allows reading at a narrow viewport", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });

  const canvas = await prepareMap(page);

  await expect(canvas.locator(".react-flow__edge.animated")).toHaveCount(0);

  const duration = await page.getByRole("button", { name: "Aumentar zoom" }).evaluate((element) => getComputedStyle(element).transitionDuration);

  expect(parseFloat(duration)).toBeLessThanOrEqual(0.00001);

  await page.getByRole("button", { name: "Lista", exact: true }).click();

  await expect(page.getByRole("list", { name: "Conceitos gerados" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await audit(page);
  await page.screenshot({ path: testInfo.outputPath("leitura-mobile.png"), fullPage: true });
});
