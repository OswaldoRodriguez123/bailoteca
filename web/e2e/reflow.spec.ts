import { expect, test } from "@playwright/test";

// Página estática prerenderizada; se usa para validar reflujo y smoke.
const publicPages = ["/", "/acerca", "/academias/latin-urban"];

async function overflowAt(page: import("@playwright/test").Page, rootPx: number) {
  return page.evaluate((px) => {
    document.documentElement.style.fontSize = `${px}px`;
    return {
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    };
  }, rootPx);
}

test("smoke: la página principal muestra su encabezado", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", { level: 1, name: "Chile baila." }),
  ).toBeVisible();
});

test.describe("reflujo a 360px", () => {
  test.use({ viewport: { width: 360, height: 800 } });

  for (const scale of [16, 20, 24, 32]) {
    test(`sin desborde horizontal con raíz de ${scale}px`, async ({
      page,
    }) => {
      for (const path of publicPages) {
        await page.goto(path, { waitUntil: "domcontentloaded" });
        const { scrollWidth, innerWidth } = await overflowAt(page, scale);
        expect(
          scrollWidth,
          `${path} desborda con raíz de ${scale}px`,
        ).toBeLessThanOrEqual(innerWidth);
      }
    });
  }
});

test.describe("reflujo a 320px", () => {
  test.use({ viewport: { width: 320, height: 800 } });

  for (const scale of [16, 32]) {
    test(`sin desborde horizontal con raíz de ${scale}px`, async ({
      page,
    }) => {
      for (const path of publicPages) {
        await page.goto(path, { waitUntil: "domcontentloaded" });
        const { scrollWidth, innerWidth } = await overflowAt(page, scale);
        expect(
          scrollWidth,
          `${path} desborda con raíz de ${scale}px`,
        ).toBeLessThanOrEqual(innerWidth);
      }
    });
  }
});
