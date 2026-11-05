import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { createNotFoundAnswer } from "../features/tutor/test-fixtures";
import { mockStudyApi, prepareMap, uploadPdf } from "./helpers/study-flow";

async function audit(page: Page) {
  const result = await new AxeBuilder({ page }).include("header").include("main")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();

  expect(result.violations).toEqual([]);
}

test("has no automatically detected violations in the initial, map, open list and tutor views", async ({ page }) => {
  await mockStudyApi(page);
  await page.goto("/");
  await audit(page);

  const { canvas } = await prepareMap(page);
  await audit(page);

  await page.getByRole("button", { name: "Lista", exact: true }).click();
  await expect(canvas).toBeHidden();
  await page.getByRole("button", { name: "Abrir todos os eixos" }).click();
  await expect(page.getByRole("list", { name: "Conceitos do eixo 1" })).toContainText("Estruturas da planta inclui Clorofila.");
  await audit(page);

  await page.getByLabel("Sua dúvida").fill("O que a clorofila faz?");
  await page.getByRole("button", { name: "Perguntar" }).click();
  await expect(page.getByRole("article", { name: "Resposta do tutor" })).toContainText("Página 2 · Seção: Cloroplastos");
  await audit(page);
});

test("blocks the upload while the AI service is unavailable and checks again on demand", async ({ page }) => {
  const api = await mockStudyApi(page, { healthy: false });
  await page.goto("/");

  await expect(page.getByText("O serviço de IA está iniciando ou indisponível.")).toBeVisible();
  await expect(page.getByLabel("Arquivo PDF")).toBeDisabled();
  await audit(page);

  api.setHealthy(true);
  await page.getByRole("button", { name: "Verificar novamente" }).click();

  await expect(page.getByText("O serviço de IA está iniciando ou indisponível.")).toHaveCount(0);
  await expect(page.getByLabel("Arquivo PDF")).toBeEnabled();
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

  await expect(page.getByRole("heading", { name: "Mapa mental da aula" })).toBeFocused();

  const toggle = page.getByRole("button", { name: "Abrir 1 conceito do eixo 1: Estruturas da planta" });
  await toggle.focus();
  await page.keyboard.press("Enter");
  const canvas = page.getByRole("region", { name: "Mapa mental interativo" });
  await expect(canvas.locator('.react-flow__node[data-id="chlorophyll"]')).toBeVisible();
  await page.getByRole("button", { name: "Fechar eixo 1: Estruturas da planta" }).focus();
  await page.keyboard.press("Space");
  await expect(canvas.locator('.react-flow__node[data-id="chlorophyll"]')).toHaveCount(0);

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
  await expect(canvas.locator('.react-flow__edge[data-id="root-topic-1"]')).toHaveAttribute("aria-label", "Relação: Fotossíntese inclui Estruturas da planta.");

  await page.keyboard.press("Escape");
  await expect(page.getByRole("complementary", { name: "Detalhes do conceito" })).toContainText("Selecione um conceito");
});

test("keeps manual positions, viewport, selection and open axes when switching between map and list", async ({ page }) => {
  const { canvas } = await prepareMap(page);
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

  await page.getByRole("button", { name: "Lista", exact: true }).click();
  await page.getByRole("button", { name: /Abrir eixo 2/ }).click();
  await page.getByRole("button", { name: "Mapa", exact: true }).click();
  await expect(canvas.locator('.react-flow__node[data-id="light-phase"]')).toBeVisible();
});

test("asks the tutor about a map concept using only the keyboard", async ({ page }) => {
  const { canvas, api } = await prepareMap(page);

  await page.getByRole("button", { name: "Abrir 1 conceito do eixo 1: Estruturas da planta" }).click();
  const concept = canvas.locator('.react-flow__node[data-id="chlorophyll"]');
  await concept.focus();
  await page.keyboard.press("Enter");

  await page.getByRole("button", { name: "Tirar dúvida sobre este conceito" }).focus();
  await page.keyboard.press("Enter");

  const question = page.getByLabel("Sua dúvida");
  await expect(question).toBeFocused();
  await expect(page.getByText("Dúvida sobre o conceito:")).toContainText("Clorofila");

  await page.keyboard.type("O que ela faz?");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Perguntar" })).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page.getByRole("article", { name: "Resposta do tutor" }).getByRole("heading", { level: 4 })).toBeFocused();
  expect(api.askBodies[0]).toMatchObject({ question: "O que ela faz?", node_id: "chlorophyll", history: [] });
});

test("explains a question outside the material and suggests concepts of the map", async ({ page }) => {
  await prepareMap(page, { answer: createNotFoundAnswer() });

  await page.getByLabel("Sua dúvida").fill("Quem ganhou a Copa de 1970?");
  await page.getByRole("button", { name: "Perguntar" }).click();

  await expect(page.getByText("Não encontrei isso no material da aula.")).toBeVisible();
  await page.getByRole("button", { name: "Perguntar sobre Clorofila" }).click();
  await expect(page.getByText("Dúvida sobre o conceito:")).toContainText("Clorofila");
  await audit(page);
});

test("recovers from ingestion and tutor errors without exposing server details", async ({ page }) => {
  await mockStudyApi(page, { answer: { status: 503 } });
  let rejectedUpload = false;
  const headers = { "access-control-allow-origin": "*" };

  await page.route("**/api/documents/ingest", async (route) => {
    if (route.request().method() === "POST" && !rejectedUpload) {
      rejectedUpload = true;
      await route.fulfill({ status: 422, headers, json: { detail: "private parser details" } });
    } else await route.fallback();
  });

  await page.goto("/");
  await uploadPdf(page);

  const alert = page.getByRole("main").getByRole("alert");
  await expect(alert).toBeFocused();
  await expect(alert).not.toContainText("private");
  await audit(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page.getByRole("region", { name: "Mapa mental interativo" })).toBeVisible();

  await page.getByLabel("Sua dúvida").fill("O que é a clorofila?");
  await page.getByRole("button", { name: "Perguntar" }).click();

  const tutorError = page.getByText("O tutor está indisponível no momento. Tente novamente em instantes.");
  await expect(tutorError).toBeFocused();
  await expect(page.getByRole("main")).not.toContainText("private detail");
  await audit(page);
});

test("respects reduced motion and allows reading at a narrow viewport", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });

  const { canvas } = await prepareMap(page);
  await expect(canvas.locator(".react-flow__edge.animated")).toHaveCount(0);

  const duration = await page.getByRole("button", { name: "Aumentar zoom" }).evaluate((element) => getComputedStyle(element).transitionDuration);
  expect(parseFloat(duration)).toBeLessThanOrEqual(0.00001);

  await page.getByRole("button", { name: "Lista", exact: true }).click();
  await expect(page.getByRole("list", { name: "Eixos de estudo" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await audit(page);
  await page.screenshot({ path: testInfo.outputPath("leitura-mobile.png"), fullPage: true });
});
