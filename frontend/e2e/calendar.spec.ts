import { expect, test } from "@playwright/test";
import { DateTime } from "luxon";

test("OAuth login and persistent family calendar lifecycle", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Entrar al calendario/ }).click();
  await expect(page.locator("#username")).toBeVisible();
  await page.locator("#username").fill("test-family");
  await page.locator("#password").fill("incorrect-password");
  await page.locator("#kc-login").click();
  await expect(
    page.getByText("Usuario o contraseña incorrectos.", { exact: true }),
  ).toBeVisible();
  await page.locator("#password").fill("Fictional-test-password-42");
  await page.locator("#kc-login").click();
  await expect(
    page.getByRole("heading", { name: "Nuestro calendario." }),
  ).toBeVisible();
  if (process.env.EXPECT_PERSISTENCE === "1") {
    await expect(
      page
        .locator(".member-button")
        .filter({ hasText: /Alex \d+/ })
        .first(),
    ).toBeVisible();
  }
  expect(await page.evaluate(() => Object.keys(localStorage))).not.toContain(
    "token",
  );

  const member = `Alex ${Date.now()}`;
  await page.getByRole("button", { name: "＋ Añadir integrante" }).click();
  await page.getByLabel("Nombre", { exact: true }).fill(member);
  await page.getByRole("button", { name: "Guardar integrante" }).click();
  await expect(
    page.getByRole("button", { name: new RegExp(member) }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "＋ Añadir evento" }).click();
  await page.getByLabel("Título", { exact: true }).fill("Clase de prueba");
  const start = DateTime.now()
    .setZone("Europe/Madrid")
    .startOf("week")
    .plus({ days: 2, hours: 9 });
  await page
    .getByLabel("Inicio", { exact: true })
    .fill(start.toFormat("yyyy-MM-dd'T'HH:mm"));
  await page
    .getByLabel("Fin", { exact: true })
    .fill(start.plus({ hours: 1 }).toFormat("yyyy-MM-dd'T'HH:mm"));
  await page.getByRole("button", { name: "Guardar evento" }).click();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toBeVisible();
  const other = `Sam ${Date.now()}`;
  await page.getByRole("button", { name: "＋ Añadir integrante" }).click();
  await page.getByLabel("Nombre", { exact: true }).fill(other);
  await page.getByRole("button", { name: "Guardar integrante" }).click();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: new RegExp(member) }).click();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toBeVisible();

  await page.locator(".fc-event", { hasText: "Clase de prueba" }).click();
  await page
    .getByLabel("Inicio", { exact: true })
    .fill(start.plus({ days: 1 }).toFormat("yyyy-MM-dd'T'HH:mm"));
  await page
    .getByLabel("Fin", { exact: true })
    .fill(start.plus({ days: 1, hours: 2 }).toFormat("yyyy-MM-dd'T'HH:mm"));
  await page.getByRole("button", { name: "Guardar evento" }).click();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toContainText("11:00");
  await page.reload();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toContainText("11:00");

  // Mouse drag moves the real calendar event and persists through the API.
  const event = page.locator(".fc-event", { hasText: "Clase de prueba" });
  const box = await event.boundingBox();
  if (!box) throw new Error("Event has no drag target");
  const save = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().includes("/api/v1/events/") &&
      response.ok(),
  );
  await page.mouse.move(box.x + 12, box.y + 18);
  await page.mouse.down();
  await page.mouse.move(box.x + 12, box.y + 118, { steps: 20 });
  await page.mouse.up();
  const moved = await (await save).json();
  expect(DateTime.fromISO(moved.starts_at).toMillis()).not.toBe(
    start.plus({ days: 1 }).toMillis(),
  );
  await page.reload();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toContainText(
    DateTime.fromISO(moved.starts_at)
      .setZone("Europe/Madrid")
      .toFormat("HH:mm"),
  );
  await page.screenshot({
    path: "test-results/calendar-desktop.png",
    fullPage: true,
  });

  await page.locator(".fc-event", { hasText: "Clase de prueba" }).click();
  await page
    .getByRole("button", { name: "Eliminar evento", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirmar eliminación" }).click();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.locator(".fc-event", { hasText: "Clase de prueba" }),
  ).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "＋ Evento" })).toBeVisible();
  await page.screenshot({
    path: "test-results/calendar-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(
    page.getByRole("button", { name: /Entrar al calendario/ }),
  ).toBeVisible();
});

test("API rejects anonymous access and password grant stays disabled", async ({
  request,
}) => {
  expect((await request.get("/api/v1/members")).status()).toBe(401);
  const response = await request.post(
    "/auth/realms/family/protocol/openid-connect/token",
    {
      form: {
        grant_type: "password",
        client_id: "family-planner",
        username: "test-family",
        password: "Fictional-test-password-42",
      },
    },
  );
  expect(response.status()).toBe(400);
  expect((await response.json()).error).toBe("unauthorized_client");
});
