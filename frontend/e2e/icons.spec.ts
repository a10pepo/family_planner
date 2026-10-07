import { expect, test } from "@playwright/test";

const iconName = "Cohete de prueba";
const image =
  "iVBORw0KGgoAAAANSUhEUgAAAEAAAAAgCAYAAACinX6EAAAAUUlEQVR4nOXOQQEAIBCAMCSrwYxjCMMY4x4swdY+7xImcRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRLndGDaB3b/Aui30bL8AAAAAElFTkSuQmCC";

// The source is a small generated color image, never a family photo.
test("uploaded icon is shared by tasks, notices and events and survives restart", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Entrar al calendario/ }).click();
  await page.locator("#username").fill("test-family");
  await page.locator("#password").fill("Fictional-test-password-42");
  await page.locator("#kc-login").click();
  await expect(page.locator(".person-heading")).toHaveCount(4);
  const tooth = page.getByRole("button", {
    name: "Lavarse los dientes, Lucía",
    exact: true,
  });
  const event = page.locator(".fc-event", {
    hasText: "Evento icono de prueba",
  });
  const notice = page.getByRole("button", {
    name: "Icono aviso de prueba, editar aviso de Jaime",
  });
  if (process.env.EXPECT_PERSISTENCE === "1") {
    await expect(tooth.locator("img.custom-symbol")).toBeVisible();
    await expect(event.locator("img.custom-symbol")).toBeVisible();
    await expect(notice.locator("img.custom-symbol")).toBeVisible();
  }
  await page.getByRole("button", { name: "Tareas", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Editar tarea Lavarse los dientes",
      exact: true,
    })
    .click();
  const choice = page.getByRole("button", {
    name: `Icono ${iconName}`,
    exact: true,
  });
  if (!(await choice.count())) {
    await page.getByLabel("Archivo del icono").setInputFiles({
      name: "invalid.svg",
      mimeType: "image/svg+xml",
      buffer: Buffer.from("<svg />"),
    });
    await expect(page.getByRole("alert")).toContainText("JPG, PNG o WebP");
    await page.getByLabel("Nombre del nuevo icono").fill(iconName);
    await page.getByLabel("Archivo del icono").setInputFiles({
      name: "test.png",
      mimeType: "image/png",
      buffer: Buffer.from(image, "base64"),
    });
    await expect(choice).toHaveAttribute("aria-pressed", "true");
    // It belongs to the shared library immediately, including when this edit is cancelled.
    await page.getByRole("button", { name: "Cancelar", exact: true }).click();
    await page
      .getByRole("button", {
        name: "Editar tarea Lavarse los dientes",
        exact: true,
      })
      .click();
  }
  await choice.click();
  await page.getByRole("button", { name: "Guardar tarea" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Editar tarea Hacer la cama", exact: true })
    .click();
  await choice.click();
  await page.getByRole("button", { name: "Guardar tarea" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Calendario", exact: true }).click();
  await expect(tooth.locator("img.custom-symbol")).toBeVisible();
  await expect(
    page
      .getByRole("button", { name: "Hacer la cama, Jaime", exact: true })
      .locator("img.custom-symbol"),
  ).toBeVisible();
  if (!(await notice.count())) {
    await page
      .getByRole("button", { name: "Añadir aviso de todo el día para Jaime" })
      .click();
    await choice.click();
    await page.getByLabel("Título del aviso").fill("Icono aviso de prueba");
    await page.getByRole("button", { name: "Guardar aviso" }).click();
  }
  await expect(notice.locator("img.custom-symbol")).toBeVisible();
  if (!(await event.count())) {
    await page
      .getByRole("button", { name: "Añadir evento para Laura" })
      .click();
    await page
      .getByLabel("Título", { exact: true })
      .fill("Evento icono de prueba");
    await page
      .getByRole("combobox", { name: "Categoría", exact: true })
      .selectOption("medical");
    await choice.click();
    await page.getByRole("button", { name: "Guardar evento" }).click();
  }
  await expect(event.locator("img.custom-symbol")).toBeVisible();
  await expect(event.locator(".event-category")).toHaveText("");
  await expect(event.locator(".event-category")).toHaveAttribute(
    "aria-label",
    "Médicos",
  );
  await expect(event.locator("strong")).toHaveCSS("font-size", "17px");
  const bounds = await event.boundingBox();
  const column = await page
    .locator(".member-calendar[data-member='Laura (Mamá)']")
    .boundingBox();
  expect(bounds!.width / column!.width).toBeGreaterThan(0.9);
  await page.reload();
  await expect(event.locator("img.custom-symbol")).toBeVisible();
  await expect(tooth.locator("img.custom-symbol")).toBeVisible();
  await page.screenshot({
    path: "test-results/icons-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(event.locator("img.custom-symbol")).toBeInViewport();
  await page.screenshot({
    path: "test-results/icons-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1360, height: 1000 });
  if (process.env.EXPECT_PERSISTENCE === "1") {
    await event.click();
    await expect(choice).toHaveAttribute("aria-pressed", "true");
    await page
      .getByRole("button", { name: "Eliminar evento", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Confirmar eliminación", exact: true })
      .click();
    await expect(event).toHaveCount(0);
    await notice.click();
    await page
      .getByRole("button", { name: "Eliminar aviso", exact: true })
      .click();
    await page
      .getByRole("button", {
        name: "Confirmar eliminación del aviso",
        exact: true,
      })
      .click();
    await page.getByRole("button", { name: "Tareas", exact: true }).click();
    for (const title of ["Lavarse los dientes", "Hacer la cama"]) {
      await page
        .getByRole("button", { name: `Editar tarea ${title}`, exact: true })
        .click();
      await page.getByRole("button", { name: title, exact: true }).click();
      await page.getByRole("button", { name: "Guardar tarea" }).click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
    }
    // The image remains available after clearing every reference.
    await page
      .getByRole("button", { name: "Crear tarea", exact: false })
      .click();
    await expect(choice).toBeVisible();
    await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  }
});
