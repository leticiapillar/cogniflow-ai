import { expect, test } from "@playwright/test";
import { createMapResponse, createProcessingStatus, createStatusResponse } from "../features/mind-map/test-fixtures";
import { mockStudyApi, prepareMap, uploadPdf } from "./helpers/study-flow";

test("opens with the theme and numbered axes, and opens an axis to show its concepts", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  const { canvas } = await prepareMap(page);

  await expect(canvas.locator('.react-flow__node[data-id="topic-1"]')).toContainText("Eixo 1");
  await expect(canvas.locator('.react-flow__node[data-id="topic-2"]')).toContainText("Eixo 2");
  await expect(canvas.locator('.react-flow__node[data-id="chlorophyll"]')).toHaveCount(0);

  await page.getByRole("button", { name: "Abrir 1 conceito do eixo 1: Estruturas da planta" }).click();

  await expect(canvas.locator(".react-flow__node")).toHaveCount(5);
  await expect(page.getByRole("button", { name: "Fechar eixo 1: Estruturas da planta" })).toHaveAttribute("aria-expanded", "true");

  await canvas.locator('.react-flow__node[data-id="chlorophyll"]').click();

  const details = page.getByRole("complementary", { name: "Detalhes do conceito" });
  await expect(details).toContainText("Pigmento que absorve luz.");
  await expect(details.getByRole("list", { name: "Relações do conceito" })).toContainText("Estruturas da planta → inclui → Clorofila");

  await page.keyboard.press("Delete");
  await expect(canvas.locator(".react-flow__node")).toHaveCount(5);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("mapa-desktop.png"), fullPage: true });

  await page.getByRole("button", { name: "Fechar eixo 1: Estruturas da planta" }).click();
  await expect(canvas.locator(".react-flow__node")).toHaveCount(3);
});

test("preserves dragged positions through selection and zoom, then restores the automatic layout", async ({ page }) => {
  const { canvas } = await prepareMap(page);
  const root = canvas.locator('.react-flow__node[data-id="root"]');

  await root.scrollIntoViewIfNeeded();

  const initial = await root.evaluate((element) => (element as HTMLElement).style.transform);
  const box = (await root.boundingBox())!;

  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 70, box.y + box.height / 2 + 45, { steps: 10 });
  await page.mouse.up();

  await expect.poll(() => root.evaluate((element) => (element as HTMLElement).style.transform)).not.toBe(initial);

  const moved = await root.evaluate((element) => (element as HTMLElement).style.transform);

  await canvas.locator('.react-flow__node[data-id="topic-2"]').click();
  await page.getByRole("button", { name: "Aumentar zoom" }).click();

  await expect.poll(() => root.evaluate((element) => (element as HTMLElement).style.transform)).toBe(moved);

  await page.getByRole("button", { name: "Reorganizar mapa" }).click();

  await expect.poll(() => root.evaluate((element) => (element as HTMLElement).style.transform)).toBe(initial);
  await expect(canvas.locator(".react-flow__edge")).toHaveCount(2);
});

test("supports zoom, pan and fitting the graph without changing its relationships", async ({ page }) => {
  const { canvas } = await prepareMap(page);
  const viewport = canvas.locator(".react-flow__viewport");
  const initial = await viewport.getAttribute("style");

  await page.getByRole("button", { name: "Aumentar zoom" }).click();
  await expect.poll(() => viewport.getAttribute("style")).not.toBe(initial);

  await page.getByRole("button", { name: "Diminuir zoom" }).click();
  await page.getByRole("button", { name: "Ajustar à tela" }).click();
  const fitted = await viewport.getAttribute("style");

  await canvas.scrollIntoViewIfNeeded();
  const box = (await canvas.boundingBox())!;

  await page.mouse.move(box.x + 15, box.y + 15);
  await page.mouse.down();
  await page.mouse.move(box.x + 65, box.y + 65, { steps: 10 });
  await page.mouse.up();

  await expect.poll(() => viewport.getAttribute("style")).not.toBe(fitted);

  await page.getByRole("button", { name: "Ajustar à tela" }).click();

  await expect.poll(() => viewport.getAttribute("style")).toBe(fitted);
  await expect(canvas.locator(".react-flow__edge")).toHaveCount(2);
});

test("shows the generation progress and then the map", async ({ page }) => {
  await mockStudyApi(page, {
    statuses: [createProcessingStatus(0, 2, "Cloroplastos"), createProcessingStatus(1, 2, "Fase clara"), createStatusResponse()],
  });
  await page.goto("/");
  await uploadPdf(page);

  await expect(page.getByText("Lendo a seção 1 de 2: Cloroplastos.")).toBeVisible();
  await expect(page.getByRole("list", { name: "Etapas da geração do mapa" }).locator("[aria-current='step']"))
    .toContainText("Ler cada seção do material");
  await expect(page.getByLabel("Sua dúvida")).toBeDisabled();

  await expect(page.getByText("Lendo a seção 2 de 2: Fase clara.")).toBeVisible();

  const canvas = page.getByRole("region", { name: "Mapa mental interativo" });
  await expect(canvas.locator(".react-flow__node")).toHaveCount(3, { timeout: 10_000 });
  await expect(page.getByRole("heading", { name: "Mapa mental da aula" })).toBeFocused();
  await expect(page.getByLabel("Sua dúvida")).toBeEnabled();
});

test("lists a section left out of a partial map and retries only that section", async ({ page }) => {
  const partial = createStatusResponse({
    status: "partial",
    failed_sections: [{ section_index: 2, section_title: "Ciclo de Calvin", reason: "invalid" }],
  });
  await prepareMap(page, { statuses: [partial], afterRetry: [createStatusResponse()] });

  await expect(page.getByText("Uma seção do material não foi processada.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Tentar de novo: Ciclo de Calvin" }).click();

  await expect(page.getByRole("list", { name: "Seções não processadas" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Mapa mental interativo" })).toBeVisible();
});

test("renders a usable canvas on a narrow screen without overflowing the page", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });

  const { canvas } = await prepareMap(page);
  await canvas.locator('.react-flow__node[data-id="root"]').click();

  await expect(page.getByRole("complementary", { name: "Detalhes do conceito" })).toContainText("Conversão de energia luminosa.");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("mapa-mobile.png"), fullPage: true });
});

test("fits five open axes on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });

  const map = createMapResponse();
  const [root, topicTemplate, conceptTemplate] = map.nodes;
  const edge = map.edges[0];
  map.nodes = [root];
  map.edges = [];
  for (let order = 1; order <= 5; order += 1) {
    const topicId = `axis-${order}`;
    map.nodes.push({ ...topicTemplate, id: topicId, data: { ...topicTemplate.data, label: `Eixo ${order}`, order } });
    map.edges.push({ ...edge, id: `root-${topicId}`, source: "root", target: topicId });
    for (let index = 1; index <= 2; index += 1) {
      const conceptId = `${topicId}-concept-${index}`;
      map.nodes.push({ ...conceptTemplate, id: conceptId, data: { ...conceptTemplate.data, label: `Conceito ${order}.${index}` } });
      map.edges.push({ ...edge, id: `${topicId}-${conceptId}`, source: topicId, target: conceptId });
    }
  }

  const { canvas } = await prepareMap(page, { statuses: [createStatusResponse({ mind_map: map })] });
  await page.getByRole("button", { name: "Abrir todos os eixos" }).click();
  await expect(canvas.locator(".react-flow__node")).toHaveCount(16);
  await page.getByRole("button", { name: "Ajustar à tela" }).click();

  const bounds = (await canvas.boundingBox())!;
  for (const node of await canvas.locator(".react-flow__node").all()) {
    const box = (await node.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(bounds.x);
    expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width);
  }
});
