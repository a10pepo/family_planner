import { expect, test, type Page } from "@playwright/test";
import { DateTime } from "luxon";

async function login(page: Page, checkIncorrectPassword = false) {
  await page.goto("/");
  await page.getByRole("button", { name: /Entrar al calendario/ }).click();
  await page.locator("#username").fill("test-family");
  if (checkIncorrectPassword) {
    await page.locator("#password").fill("incorrect-password");
    await page.locator("#kc-login").click();
    await expect(
      page.getByText("Usuario o contraseña incorrectos.", { exact: true }),
    ).toBeVisible();
  }
  await page.locator("#password").fill("Fictional-test-password-42");
  await page.locator("#kc-login").click();
  await expect(
    page.getByRole("region", { name: "Calendario diario por familiar" }),
  ).toBeVisible();
  await expect(page.locator(".person-heading")).toHaveCount(4);
}

test("daily demo has four faces and persistent categorized events", async ({
  page,
}) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await login(page, true);
  const names = ["Laura", "Pedro", "Jaime", "Lucía"];
  await expect(page.locator(".person-name")).toHaveText(names);
  await expect(page.locator(".person-nickname")).toHaveText([
    "Mamá",
    "Papá",
    "Tete",
    "Teta",
  ]);
  for (const name of names)
    await expect(
      page.getByRole("img", {
        name: new RegExp(`^(Cara ilustrada|Foto) de ${name}$`),
      }),
    ).toBeVisible();
  await expect(
    page.getByText("Nuestro calendario", { exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("LA FAMILIA", { exact: true })).toHaveCount(0);
  await expect(page.locator(".sidebar")).toHaveCSS("width", "76px");
  await expect(
    page.locator(".sidebar").getByRole("button", { name: "Eventos" }),
  ).toHaveCount(1);
  await expect(page.locator(".view-badge.selected")).toHaveText("Día");
  if (process.env.EXPECT_PERSISTENCE === "1") {
    await expect(
      page.locator(".member-calendar[data-member='Jaime (Tete)'] .fc-event", {
        hasText: "Fútbol",
      }),
    ).toBeVisible();
  }
  expect(await page.evaluate(() => Object.keys(localStorage))).not.toContain(
    "token",
  );

  const column = page.locator(".member-calendar[data-member='Laura (Mamá)']");
  await column.locator('.fc-timegrid-slot-lane[data-time="13:00:00"]').click();
  await expect(
    page.getByRole("heading", { name: "Nuevo evento" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("combobox", { name: "Integrante", exact: true })
      .locator("option:checked"),
  ).toHaveText("Laura (Mamá)");
  const title = `Plan de prueba ${Date.now()}`;
  await page.getByLabel("Título", { exact: true }).fill(title);
  await page
    .getByRole("combobox", { name: "Categoría", exact: true })
    .selectOption("school");
  await page.getByRole("button", { name: "Guardar evento" }).click();
  const event = column.locator(".fc-event", { hasText: title });
  await expect(event).toBeVisible();
  await expect(event).toHaveCSS("background-color", "rgb(220, 232, 250)");
  await expect(event.locator(".event-category")).toHaveAttribute(
    "aria-label",
    "Colegio",
  );
  await expect(event.locator(".event-category svg")).toHaveCount(1);
  await expect(
    page.locator(".member-calendar[data-member='Pedro (Papá)'] .fc-event", {
      hasText: title,
    }),
  ).toHaveCount(0);
  await page.reload();
  await expect(event).toBeVisible();
  await event.click();
  await expect(
    page.getByRole("combobox", { name: "Categoría", exact: true }),
  ).toHaveValue("school");
  const start = DateTime.now()
    .setZone("Europe/Madrid")
    .startOf("day")
    .plus({ hours: 12 });
  await page
    .getByLabel("Hora de inicio", { exact: true })
    .fill(start.toFormat("HH:mm"));
  await page
    .getByLabel("Hora de fin", { exact: true })
    .fill(start.plus({ hours: 1 }).toFormat("HH:mm"));
  await page
    .getByRole("combobox", { name: "Categoría", exact: true })
    .selectOption("friends");
  await page.getByRole("button", { name: "Guardar evento" }).click();
  await expect(event).toHaveCSS("background-color", "rgb(231, 222, 244)");
  await expect(event.locator(".event-category")).toHaveAttribute(
    "aria-label",
    "Amigos",
  );

  const box = await event.boundingBox();
  if (!box) throw new Error("Event has no drag target");
  const save = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().includes("/api/v1/events/") &&
      response.ok(),
  );
  await page.mouse.move(box.x + 15, box.y + 18);
  await page.mouse.down();
  await page.mouse.move(box.x + 15, box.y + 100, { steps: 20 });
  await page.mouse.up();
  const moved = await (await save).json();
  expect(DateTime.fromISO(moved.starts_at).toMillis()).not.toBe(
    start.toMillis(),
  );
  expect(moved.category).toBe("friends");
  await page.reload();
  await expect(event).toContainText(
    DateTime.fromISO(moved.starts_at)
      .setZone("Europe/Madrid")
      .toFormat("HH:mm"),
  );
  await expect(event.locator(".event-category")).toHaveAttribute(
    "aria-label",
    "Amigos",
  );

  await page.getByRole("button", { name: "Día siguiente" }).click();
  await expect(event).toHaveCount(0);
  await page.getByRole("button", { name: "Día anterior" }).click();
  await expect(event).toBeVisible();
  await page.screenshot({
    path: "test-results/calendar-desktop.png",
    fullPage: true,
  });
  await event.click();
  await page
    .getByRole("button", { name: "Eliminar evento", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirmar eliminación" }).click();
  await expect(event).toHaveCount(0);
  await page.reload();
  await expect(event).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  const mobileCalendar = page.locator(".mobile-day-calendar");
  await expect(mobileCalendar).toBeVisible();
  const columnDates = await mobileCalendar
    .locator(".fc-timegrid-col[data-date]")
    .evaluateAll((columns) => [
      ...new Set(columns.map((column) => column.getAttribute("data-date"))),
    ]);
  expect(columnDates).toHaveLength(1);
  await expect(page.locator(".mobile-day-member-filter")).toHaveCount(4);
  await expect(page.locator(".person-heading")).toHaveCount(0);
  await expect(page.locator(".task-token")).toHaveCount(0);
  await expect(page.locator(".sidebar")).toHaveCSS("width", "60px");
  await expect(
    page.getByRole("button", { name: "Añadir evento familiar de todo el día" }),
  ).toBeHidden();
  await expect(page.locator(".calendar-date-mobile")).toHaveCSS(
    "white-space",
    "nowrap",
  );
  const slot = mobileCalendar.locator(
    '.fc-timegrid-slot-lane[data-time="09:00:00"]',
  );
  await slot.scrollIntoViewIfNeeded();
  const slotBounds = await slot.boundingBox();
  const columnBounds = await mobileCalendar
    .locator(".fc-timegrid-col")
    .first()
    .boundingBox();
  await page.mouse.click(
    columnBounds!.x + columnBounds!.width / 2,
    slotBounds!.y + 8,
  );
  await expect(
    page.getByRole("heading", { name: "Nuevo evento" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await page.screenshot({
    path: "test-results/calendar-mobile.png",
    fullPage: true,
  });
  expect(browserErrors).toEqual([]);
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
