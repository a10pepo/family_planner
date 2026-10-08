import { expect, test, type Page } from "@playwright/test";
import { DateTime } from "luxon";

async function login(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /Entrar al calendario/ }).click();
  await page.locator("#username").fill("test-family");
  await page.locator("#password").fill("Fictional-test-password-42");
  await page.locator("#kc-login").click();
  await expect(page.locator(".person-heading")).toHaveCount(4);
}

test("large portraits and vertical routines accompany a moving current-time line", async ({
  page,
}) => {
  await page.clock.install();
  await login(page);
  const jaime = page
    .locator(".person-heading")
    .filter({ has: page.locator(".person-name", { hasText: /^Jaime$/ }) });
  const portrait = jaime.locator(".face-avatar");
  await expect(portrait).toHaveCSS("width", "116px");
  const routines = jaime.locator(".task-token");
  const picture = await portrait.boundingBox();
  const first = await routines.nth(0).boundingBox();
  const second = await routines.nth(1).boundingBox();
  expect(first!.width).toBe(64);
  expect(first!.x + first!.width).toBeLessThan(picture!.x);
  expect(second!.y).toBeGreaterThan(first!.y);
  const line = page.locator(".current-time-line");
  await expect(line).toHaveCount(1);
  const initial = await line.evaluate((element) =>
    parseFloat((element as HTMLElement).style.top),
  );
  await page.clock.fastForward(16000);
  if (await line.count()) {
    const updated = await line.evaluate((element) =>
      parseFloat((element as HTMLElement).style.top),
    );
    expect(updated).toBeGreaterThan(initial);
  } else {
    // Midnight must remove yesterday's indicator rather than keep a stale line.
    await page.getByRole("button", { name: "Hoy", exact: true }).click();
    await expect(line).toHaveCount(1);
  }
  await page.getByRole("button", { name: "Día siguiente" }).click();
  await expect(line).toHaveCount(0);
});

test("week filters, global all-day events and confirmed profile archive persist", async ({
  page,
}) => {
  const birthday = "Cumpleaños familiar de prueba";
  const person = "Integrante de archivo de prueba";
  const plan = "Plan semanal de prueba";
  await login(page);
  const token = page.getByRole("button", {
    name: `Editar evento familiar ${birthday}`,
    exact: true,
  });
  if (process.env.EXPECT_PERSISTENCE === "1") {
    await expect(token).toBeVisible();
    await page
      .getByRole("button", { name: "Configuración", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: `Restaurar integrante ${person}` }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Calendario", exact: true }).click();
  }
  if (!(await token.count())) {
    await page
      .getByRole("button", { name: "Añadir evento familiar de todo el día" })
      .click();
    await page.getByLabel("Título del evento familiar").fill(birthday);
    await page.getByRole("button", { name: "Cumpleaños", exact: true }).click();
    await page.getByRole("button", { name: "Guardar evento familiar" }).click();
  }
  await expect(token).toBeVisible();
  await page.reload();
  await expect(token).toBeVisible();
  await page.getByRole("button", { name: "Día siguiente" }).click();
  await expect(token).toHaveCount(0);
  await page.getByRole("button", { name: "Día anterior" }).click();
  await page.getByRole("button", { name: "Semana", exact: true }).click();
  const calendar = page.locator(".week-calendar");
  const start = DateTime.now().setZone("Europe/Madrid").startOf("week");
  await expect(calendar.locator(".fc-col-header-cell")).toHaveCount(7);
  for (let day = 0; day < 7; day++)
    await expect(
      calendar.locator(".fc-col-header-cell").nth(day),
    ).toHaveAttribute("data-date", start.plus({ days: day }).toISODate()!);
  await expect(page.locator(".task-token")).toHaveCount(0);
  await expect(
    calendar.locator(".fc-daygrid-event", { hasText: birthday }),
  ).toBeVisible();
  if (!(await calendar.locator(".fc-event", { hasText: plan }).count())) {
    const slot = calendar.locator(
      '.fc-timegrid-slot-lane[data-time="20:00:00"]',
    );
    await slot.scrollIntoViewIfNeeded();
    const slotBounds = await slot.boundingBox();
    const columnBounds = await calendar
      .locator(
        `.fc-timegrid-col[data-date='${DateTime.now().setZone("Europe/Madrid").toISODate()}']`,
      )
      .boundingBox();
    await page.mouse.click(
      columnBounds!.x + columnBounds!.width / 2,
      slotBounds!.y + 8,
    );
    await expect(
      page.getByRole("heading", { name: "Nuevo evento", exact: true }),
    ).toBeVisible();
    await page.getByLabel("Título", { exact: true }).fill(plan);
    await page
      .getByRole("combobox", { name: "Integrante", exact: true })
      .selectOption({ label: "Laura (Mamá)" });
    const begins = DateTime.now()
      .setZone("Europe/Madrid")
      .startOf("day")
      .plus({ hours: 12 });
    await page
      .getByLabel("Inicio", { exact: true })
      .fill(begins.toFormat("yyyy-MM-dd'T'HH:mm"));
    await page
      .getByLabel("Fin", { exact: true })
      .fill(begins.plus({ hours: 1 }).toFormat("yyyy-MM-dd'T'HH:mm"));
    await page
      .getByRole("button", { name: "Guardar evento", exact: true })
      .click();
  }
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const event = calendar.locator(".fc-event", { hasText: plan });
  await calendar
    .locator(".fc-scroller-liquid-absolute")
    .evaluateAll((elements) => {
      for (const element of elements) element.scrollTop = 7 * 56;
    });
  await expect(event).toBeVisible();
  const filter = page.getByRole("button", {
    name: "Mostrar eventos de Laura (Mamá)",
  });
  await filter.click();
  await expect(filter).toHaveAttribute("aria-pressed", "false");
  await expect(event).toHaveCount(0);
  await expect(
    calendar.locator(".fc-daygrid-event", { hasText: birthday }),
  ).toBeVisible();
  await filter.click();
  await expect(event).toBeVisible();
  const previous = start.minus({ weeks: 1 });
  await page.getByRole("button", { name: "Semana anterior" }).click();
  await expect(calendar.locator(".fc-col-header-cell").first()).toHaveAttribute(
    "data-date",
    previous.toISODate()!,
  );
  await page.getByRole("button", { name: "Semana siguiente" }).click();
  await expect(event).toBeVisible();
  await page.screenshot({
    path: "test-results/week-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".week-viewport").evaluate((element) => {
    element.scrollLeft = element.scrollWidth;
  });
  await expect(calendar.locator(".fc-col-header-cell").last()).toBeInViewport();
  await page.screenshot({
    path: "test-results/week-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1360, height: 1000 });
  await page.getByRole("button", { name: "Día", exact: true }).click();
  await expect(page.locator(".person-heading")).toHaveCount(4);
  await page
    .getByRole("button", { name: "Configuración", exact: true })
    .click();
  const restore = page.getByRole("button", {
    name: `Restaurar integrante ${person}`,
  });
  if (!(await restore.count())) {
    await page
      .getByRole("button", { name: "Añadir integrante", exact: true })
      .click();
    await page.getByLabel("Nombre", { exact: true }).fill(person);
    await page.getByRole("button", { name: "Guardar integrante" }).click();
  } else await restore.click();
  const retire = page.getByRole("button", {
    name: `Retirar integrante ${person}`,
  });
  await expect(retire).toBeVisible();
  await retire.click();
  await page.getByRole("button", { name: "Conservar integrante" }).click();
  await expect(retire).toBeVisible();
  await page.getByRole("button", { name: "Calendario", exact: true }).click();
  await expect(page.locator(".person-heading")).toHaveCount(5);
  await page
    .getByRole("button", { name: "Configuración", exact: true })
    .click();
  await retire.click();
  await page
    .getByRole("button", { name: "Confirmar retiro", exact: true })
    .click();
  await expect(restore).toBeVisible();
  await page.getByRole("button", { name: "Calendario", exact: true }).click();
  await expect(page.locator(".person-heading")).toHaveCount(4);
  await page.reload();
  await expect(page.locator(".person-heading")).toHaveCount(4);
  if (process.env.EXPECT_PERSISTENCE === "1") {
    await page
      .getByRole("button", { name: "Configuración", exact: true })
      .click();
    await restore.click();
    await expect(retire).toBeVisible();
    await retire.click();
    await page
      .getByRole("button", { name: "Confirmar retiro", exact: true })
      .click();
    await page.getByRole("button", { name: "Calendario", exact: true }).click();
    await token.click();
    await page
      .getByRole("button", { name: "Eliminar evento familiar", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Conservar evento familiar", exact: true })
      .click();
    await page
      .getByLabel("Título del evento familiar")
      .fill(`${birthday} editado`);
    await page.getByRole("button", { name: "Guardar evento familiar" }).click();
    await page
      .getByRole("button", {
        name: `Editar evento familiar ${birthday} editado`,
        exact: true,
      })
      .click();
    await page
      .getByRole("button", { name: "Eliminar evento familiar", exact: true })
      .click();
    await page
      .getByRole("button", {
        name: "Confirmar eliminación del evento familiar",
        exact: true,
      })
      .click();
    await expect(token).toHaveCount(0);
    await page.getByRole("button", { name: "Semana", exact: true }).click();
    await event.click();
    await page
      .getByRole("button", { name: "Eliminar evento", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Confirmar eliminación", exact: true })
      .click();
    await expect(event).toHaveCount(0);
  }
});
