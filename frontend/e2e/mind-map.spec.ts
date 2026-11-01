import { expect, test } from "@playwright/test";
import { createMapResponse } from "../features/mind-map/test-fixtures";
import { prepareMap } from "./helpers/study-flow";

test("renders the API concepts and relationships and opens complete concept details", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  const canvas = await prepareMap(page);

  await canvas.locator('.react-flow__node[data-id="chlorophyll"]').click();

  const details = page.getByRole("complementary", { name: "Detalhes do conceito" });

  await expect(details).toContainText("Pigmento que absorve luz.");
  await expect(details.getByRole("list", { name: "Relações do conceito" })).toContainText("Fotossíntese → utiliza → Clorofila");
  await expect(canvas.locator('.react-flow__edge[data-id="root-chlorophyll"]')).toBeVisible();

  await page.keyboard.press("Delete");

  await expect(canvas.locator(".react-flow__node")).toHaveCount(2);
  await expect(canvas.locator(".react-flow__edge")).toHaveCount(1);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("mapa-desktop.png"), fullPage: true });
});

test("preserves dragged positions through selection and zoom, then restores the automatic layout", async ({ page }) => {
  const canvas = await prepareMap(page);
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

  await canvas.locator('.react-flow__node[data-id="chlorophyll"]').click();
  await page.getByRole("button", { name: "Aumentar zoom" }).click();

  await expect.poll(() => root.evaluate((element) => (element as HTMLElement).style.transform)).toBe(moved);

  await page.getByRole("button", { name: "Reorganizar mapa" }).click();

  await expect.poll(() => root.evaluate((element) => (element as HTMLElement).style.transform)).toBe(initial);
  await expect(canvas.locator(".react-flow__edge")).toHaveCount(1);
});

test("supports zoom, pan and fitting the graph without changing its relationships", async ({ page }) => {
  const canvas = await prepareMap(page);
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
  await expect(canvas.locator(".react-flow__edge")).toHaveCount(1);
});

test("resets the graph and selection for a newly generated result", async ({ page }) => {
  const canvas = await prepareMap(page);

  await canvas.locator('.react-flow__node[data-id="chlorophyll"]').click();

  await expect(page.getByRole("complementary", { name: "Detalhes do conceito" })).toContainText("Pigmento que absorve luz.");

  await page.getByLabel("O que você quer estudar?").fill("Outro tema de estudo");

  await expect(canvas).toHaveCount(0);

  await page.getByRole("button", { name: "Gerar mapa", exact: true }).click();

  await expect(canvas.locator(".react-flow__edge")).toHaveCount(1);
  await expect(page.getByRole("complementary", { name: "Detalhes do conceito" })).toContainText("Selecione um conceito");
});

test("renders a usable canvas on a narrow screen without overflowing the page", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });

  const canvas = await prepareMap(page);

  await canvas.locator('.react-flow__node[data-id="root"]').click();

  await expect(page.getByRole("complementary", { name: "Detalhes do conceito" })).toContainText("Conversão de energia luminosa.");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("mapa-mobile.png"), fullPage: true });
});

test("fits a branched graph on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });

  const map = createMapResponse();
  const template = map.nodes[1];

  map.nodes = [map.nodes[0], ...Array.from({ length: 8 }, (_, index) => ({
    ...template, id: `concept-${index}`, data: { ...template.data, label: `Conceito ${index + 1}` },
  }))];
  map.edges = map.nodes.slice(1).map((node) => ({ ...map.edges[0], id: `root-${node.id}`, target: node.id }));

  const canvas = await prepareMap(page, map);

  await page.getByRole("button", { name: "Ajustar à tela" }).click();

  const bounds = (await canvas.boundingBox())!;

  for (const node of await canvas.locator(".react-flow__node").all()) {
    const box = (await node.boundingBox())!;

    expect(box.x).toBeGreaterThanOrEqual(bounds.x);
    expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width);
  }
});
