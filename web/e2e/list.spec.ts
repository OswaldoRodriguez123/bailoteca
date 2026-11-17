import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

// E2E de la lista con la API mockeada vía interceptación de rutas:
// determinista y sin tocar la API de producción.
//
// OJO: el HTML prerenderizado embebe las respuestas del build en
// TransferState (`ng-state`), así que la carga inicial NO dispara una
// consulta de red: muestra los datos del build. Por eso cada test provoca
// una interacción (o un deep link) que sí consulta al cliente con
// parámetros distintos a los del build.
//
// La URL de la API sale del mismo site.config.json que alimenta el build
// (y respeta el override API_BASE_URL de scripts/write-env.mjs). La
// normalización replica la del servicio (quita UNA barra final) para que
// el mock coincida con la app incluso con config patológica.
const config = JSON.parse(
  readFileSync(join(__dirname, "..", "site.config.json"), "utf8"),
);
const baseUrl = (process.env.API_BASE_URL ?? config.apiBaseUrl).replace(
  /\/$/,
  "",
);

const apiRoute = (path: string) => (url: URL) =>
  url.href.startsWith(`${baseUrl}${path}`);

const STYLES = [
  { slug: "salsa", name: "Salsa", sort: 1 },
  { slug: "bachata", name: "Bachata", sort: 2 },
];

const COMUNAS = ["Maipú", "Providencia"];

let seq = 0;
function makeAcademy(overrides: Record<string, unknown> = {}) {
  seq += 1;
  return {
    id: overrides.id ?? `e2e-${seq}`,
    slug: overrides.slug ?? `academia-e2e-${seq}`,
    name: overrides.name ?? "Academia E2E",
    description: null,
    status: "published",
    source_urls: [],
    cover_url: null,
    created_at: null,
    updated_at: null,
    verified_at: null,
    locations: [],
    links: [],
    styles: [],
    google: null,
    ...overrides,
  };
}

const danzaCasa = makeAcademy({
  id: "1",
  slug: "danza-casa",
  name: "Danza Casa",
  description: "Clases de salsa en Maipú.",
  locations: [
    {
      label: null,
      address: "Plaza de Maipú",
      comuna: "Maipú",
      lat: null,
      lng: null,
      source_url: null,
    },
  ],
  styles: [{ slug: "salsa", name: "Salsa", confidence: null, evidence: null }],
});

const ritmoNorte = makeAcademy({
  id: "2",
  slug: "ritmo-norte",
  name: "Ritmo Norte",
  description: "Bachata y salsa en Providencia.",
  locations: [
    {
      label: null,
      address: "Pedro de Valdivia",
      comuna: "Providencia",
      lat: null,
      lng: null,
      source_url: null,
    },
  ],
  styles: [
    { slug: "salsa", name: "Salsa", confidence: null, evidence: null },
    { slug: "bachata", name: "Bachata", confidence: null, evidence: null },
  ],
});

const DEFAULT_ITEMS = [danzaCasa, ritmoNorte];

interface MockOptions {
  items?: unknown[];
  total?: number;
  // Fallos 500 antes de responder OK (para el flujo de error + reintento).
  failTimes?: number;
}

async function installApi(page: Page, options: MockOptions = {}) {
  const academiesUrls: string[] = [];
  let failuresLeft = options.failTimes ?? 0;
  const items = options.items ?? DEFAULT_ITEMS;
  const total = options.total ?? items.length;

  await page.route(
    apiRoute("/academies"),
    async (route) => {
      academiesUrls.push(route.request().url());
      if (failuresLeft > 0) {
        failuresLeft -= 1;
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "boom" }),
        });
        return;
      }
      const url = new URL(route.request().url());
      const pageParam = Number(url.searchParams.get("page") ?? "1");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items,
          page: pageParam,
          page_size: 20,
          total,
        }),
      });
    },
  );

  await page.route(
    apiRoute("/styles"),
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: STYLES }),
      }),
  );

  await page.route(
    apiRoute("/comunas"),
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: COMUNAS }),
      }),
  );

  return academiesUrls;
}

test("carga la página con encabezado, filtros y contador", async ({ page }) => {
  await installApi(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByRole("heading", { level: 1, name: "Chile baila." }),
  ).toBeVisible();
  await expect(page.getByLabel("Filtros del directorio")).toBeVisible();
  // El contenido proviene del TransferState del build: el total varía.
  await expect(page.getByText(/\d+ academias?/)).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("la búsqueda con debounce actualiza la URL, reconsulta y pinta fixtures", async ({
  page,
}) => {
  const urls = await installApi(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });

  await page.locator("#filter-q").fill("salsa");

  await expect(page).toHaveURL(/[?&]q=salsa(&|$)/);
  await expect
    .poll(() => urls.filter((u) => u.includes("q=salsa")).length)
    .toBeGreaterThan(0);
  await expect(page.getByRole("link", { name: /Danza Casa/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Ritmo Norte/ })).toBeVisible();
});

test("filtrar por región actualiza la URL y reconsulta con fixtures", async ({
  page,
}) => {
  const urls = await installApi(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });

  await page.locator("#filter-region").selectOption("valparaiso");

  await expect(page).toHaveURL(/[?&]region=valparaiso/);
  await expect
    .poll(() => urls.filter((u) => u.includes("region=valparaiso")).length)
    .toBeGreaterThan(0);
  await expect(page.getByRole("link", { name: /Danza Casa/ })).toBeVisible();
});

test("filtrar por estilo actualiza la URL y reconsulta con fixtures", async ({
  page,
}) => {
  const urls = await installApi(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });

  // Las opciones vienen del build (TransferState); selecciono por etiqueta
  // y aserto con el valor real que el select devuelve.
  const [value] = await page
    .locator("#filter-estilo")
    .selectOption({ label: "Bachata" });

  await expect(page).toHaveURL(new RegExp(`[?&]style=${value}`));
  await expect
    .poll(() => urls.filter((u) => u.includes(`style=${value}`)).length)
    .toBeGreaterThan(0);
  await expect(page.getByRole("link", { name: /Danza Casa/ })).toBeVisible();
});

test("limpiar filtros vuelve al inicio y restaura la consulta por defecto", async ({
  page,
}) => {
  const urls = await installApi(page);
  await page.goto("/?region=valparaiso&style=salsa", {
    waitUntil: "domcontentloaded",
  });
  await expect(page).toHaveURL(/region=valparaiso/);

  await page.getByRole("button", { name: "Limpiar filtros" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect
    .poll(() => urls[urls.length - 1] ?? "")
    .toContain("region=metropolitana");
});

test("la paginación enlaza a la siguiente página", async ({ page }) => {
  const urls = await installApi(page, { total: 45 });
  // Deep link a una página ≠ 1: no está en el TransferState del build.
  await page.goto("/?page=2", { waitUntil: "domcontentloaded" });

  await expect(page.getByText("Página 2 de 3")).toBeVisible();
  await page.getByRole("link", { name: "Siguiente →" }).click();

  await expect(page).toHaveURL(/[?&]page=3/);
  await expect(page.getByText("Página 3 de 3")).toBeVisible();
  expect(urls.some((u) => u.includes("page=3"))).toBe(true);
});

test("error al cargar muestra una alerta y reintentar recupera el listado", async ({
  page,
}) => {
  // Deep link con parámetro no cacheado (sort=nombre) para forzar fetch.
  const urls = await installApi(page, { failTimes: 1 });
  await page.goto("/?sort=nombre", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("alert")).toContainText("Algo salió mal");
  expect(urls).toHaveLength(1);

  await page.getByRole("button", { name: "Reintentar" }).click();

  await expect(page.getByRole("link", { name: /Danza Casa/ })).toBeVisible();
  expect(urls).toHaveLength(2);
});

test("sin resultados muestra el estado vacío y limpiar filtros funciona", async ({
  page,
}) => {
  await installApi(page, { items: [], total: 0 });
  // Deep link para saltar el TransferState y recibir el vacío del mock.
  await page.goto("/?q=zzz&style=salsa", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByRole("heading", { name: "Sin resultados" }),
  ).toBeVisible();
  // Hay dos "Limpiar filtros" (barra de filtros y estado vacío); el del
  // estado vacío es el último en el DOM.
  await page
    .getByRole("button", { name: "Limpiar filtros" })
    .last()
    .click();

  await expect(page).toHaveURL(/\/$/);
});
