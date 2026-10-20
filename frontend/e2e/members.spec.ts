import { expect, test } from "@playwright/test";

const addedMember = "Integrante temporal";

test("settings can add and persist additional family members", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Entrar al calendario/ }).click();
  await page.locator("#username").fill("test-family");
  await page.locator("#password").fill("Fictional-test-password-42");
  await page.locator("#kc-login").click();
  await expect(page.locator(".person-heading")).toHaveCount(4);

  await page
    .getByRole("button", { name: "Configuración", exact: true })
    .click();
  await page
    .locator(".management-heading")
    .getByRole("button", { name: "Añadir integrante" })
    .click();
  await page.getByLabel("Nombre", { exact: true }).fill(addedMember);
  await page.getByRole("button", { name: "Guardar integrante" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: addedMember })).toBeVisible();

  await page.reload();
  await expect(page.locator(".person-heading")).toHaveCount(5);
  await page
    .getByRole("button", { name: "Configuración", exact: true })
    .click();
  await page
    .getByRole("button", { name: `Retirar integrante ${addedMember}` })
    .click();
  await page.getByRole("button", { name: "Confirmar retiro" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Integrantes archivados" }),
  ).toBeVisible();
});
