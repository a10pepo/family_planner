import { expect, test, type Page } from "@playwright/test";

const routine = "Rutina de persistencia";
const notice = "Excursión de prueba";

async function login(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /Entrar al calendario/ }).click();
  await page.locator("#username").fill("test-family");
  await page.locator("#password").fill("Fictional-test-password-42");
  await page.locator("#kc-login").click();
  await expect(page.locator(".person-heading")).toHaveCount(4);
}

test("profiles, day notices and independent recurring tasks survive reload and restart", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page);
  if (process.env.EXPECT_PERSISTENCE === "1")
    await expect(
      page.getByRole("img", { name: "Foto de Laura" }),
    ).toBeVisible();
  await page
    .getByRole("button", { name: "Configuración", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Editar perfil de Laura (Mamá)" })
    .click();
  await page.getByLabel("Nombre", { exact: true }).fill("Laura prueba (Mamá)");
  // A persisted preview must not satisfy the wait for the newly uploaded photo.
  const removePhoto = page.getByRole("button", { name: "Quitar foto" });
  if (await removePhoto.count()) await removePhoto.click();
  await expect(removePhoto).toHaveCount(0);
  await page.getByLabel("Foto del integrante").setInputFiles({
    name: "synthetic.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAEAAAAAgCAIAAAAt/+nTAAAAUUlEQVR4nNXOQREAIAzAsFL/StCCFjQgYg+uUZC1z6VM4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iTO34GpB8cYAqSNE0TuAAAAAElFTkSuQmCC",
      "base64",
    ),
  });
  await expect(page.getByRole("button", { name: "Quitar foto" })).toBeEnabled();
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await expect(
    page.getByRole("heading", { name: "Laura prueba (Mamá)" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole("img", { name: "Foto de Laura" })).toBeVisible();
  const photo = page.getByRole("img", { name: "Foto de Laura" });
  expect(
    await photo.evaluate((image) => (image as HTMLImageElement).naturalWidth),
  ).toBe(256);
  await page
    .getByRole("button", { name: "Configuración", exact: true })
    .click();
  await page.screenshot({
    path: "test-results/settings-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Editar perfil de Laura prueba (Mamá)" })
    .click();
  await page.getByLabel("Nombre", { exact: true }).fill("Laura (Mamá)");
  if (process.env.EXPECT_PERSISTENCE === "1")
    await page.getByRole("button", { name: "Quitar foto" }).click();
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await expect(
    page.getByRole("heading", { name: "Laura (Mamá)" }),
  ).toBeVisible();

  const lucia = page.getByRole("button", {
    name: `${routine}, Lucía`,
    exact: true,
  });
  const jaime = page.getByRole("button", {
    name: `${routine}, Jaime`,
    exact: true,
  });
  const alert = page.getByRole("button", {
    name: `${notice}, editar aviso de Jaime`,
  });
  await page.getByRole("button", { name: "Calendario", exact: true }).click();
  if (process.env.EXPECT_PERSISTENCE === "1") {
    await expect(lucia).toHaveAttribute("aria-pressed", "true");
    await expect(jaime).toHaveAttribute("aria-pressed", "false");
    await expect(alert).toBeVisible();
  } else {
    // Repeatable on the same isolated test stack: reuse an earlier test fixture.
    await page.getByRole("button", { name: "Tareas", exact: true }).click();
    const existing = page.getByRole("button", {
      name: `Editar tarea ${routine}`,
      exact: true,
    });
    if (!(await existing.count())) {
      await page.getByRole("button", { name: /Crear tarea/ }).click();
      await expect(
        page.getByRole("button", { name: "Guardar tarea" }),
      ).toBeDisabled();
      await page
        .getByRole("button", { name: "Hacer la cama", exact: true })
        .click();
      await page.getByLabel("Nombre de la tarea").fill(routine);
      await page.getByLabel("Jaime (Tete)", { exact: true }).check();
      await page.getByLabel("Lucía (Teta)", { exact: true }).check();
      await page.getByRole("button", { name: "Guardar tarea" }).click();
    }
    await expect(existing).toBeVisible();
    // Editing the definition retains assignments and marks.
    await existing.click();
    await expect(
      page.getByLabel("Lucía (Teta)", { exact: true }),
    ).toBeChecked();
    await page.getByRole("button", { name: "Guardar tarea" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.screenshot({
      path: "test-results/tasks-desktop.png",
      fullPage: true,
    });
    await page.getByRole("button", { name: "Calendario", exact: true }).click();
    await expect(lucia).toBeVisible();
    if ((await lucia.getAttribute("aria-pressed")) === "false")
      await lucia.click();
    if ((await jaime.getAttribute("aria-pressed")) === "true")
      await jaime.click();
    if (!(await alert.count())) {
      await page
        .getByRole("button", { name: "Añadir aviso de todo el día para Jaime" })
        .click();
      await page
        .getByRole("button", { name: "Excursión", exact: true })
        .click();
      await page.getByLabel("Título del aviso").fill(notice);
      await page.getByRole("button", { name: "Guardar aviso" }).click();
    }
  }
  await expect(lucia).toHaveAttribute("aria-pressed", "true");
  await expect(jaime).toHaveAttribute("aria-pressed", "false");
  await page.reload();
  await expect(lucia).toHaveAttribute("aria-pressed", "true");
  await expect(alert).toBeVisible();
  await page.getByRole("button", { name: "Día siguiente" }).click();
  await expect(lucia).toHaveAttribute("aria-pressed", "false");
  await expect(jaime).toHaveAttribute("aria-pressed", "false");
  await expect(alert).toHaveCount(0);
  await page.getByRole("button", { name: "Día anterior" }).click();
  await expect(lucia).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({
    path: "test-results/daily-features-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobileFilter = page
    .locator(".mobile-day-member-filter")
    .filter({ hasText: "Lucía" });
  await expect(page.locator(".mobile-day-calendar")).toBeVisible();
  await expect(page.locator(".task-token")).toHaveCount(0);
  await expect(mobileFilter).toBeInViewport();
  await expect(mobileFilter).toHaveAttribute("aria-pressed", "true");
  const bounds = await mobileFilter.boundingBox();
  expect(bounds!.width).toBeGreaterThanOrEqual(44);
  expect(bounds!.height).toBeGreaterThanOrEqual(44);
  await mobileFilter.click();
  await expect(mobileFilter).toHaveAttribute("aria-pressed", "false");
  await mobileFilter.click();
  await expect(mobileFilter).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({
    path: "test-results/daily-features-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator(".day-viewport").evaluate((element) => {
    element.scrollLeft = 0;
  });
  if (process.env.EXPECT_PERSISTENCE === "1") {
    await alert.click();
    await expect(page.getByLabel("Título del aviso")).toHaveValue(notice);
    await page
      .getByRole("button", { name: "Eliminar aviso", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Confirmar eliminación del aviso" })
      .click();
    await expect(alert).toHaveCount(0);
    await page.getByRole("button", { name: "Tareas", exact: true }).click();
    await page
      .getByRole("button", { name: `Archivar tarea ${routine}`, exact: true })
      .click();
    await page.getByRole("button", { name: "Confirmar archivo" }).click();
    await expect(
      page.getByRole("button", {
        name: `Editar tarea ${routine}`,
        exact: true,
      }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Calendario", exact: true }).click();
    await expect(lucia).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});
