import { describe, expect, it } from "vitest";
import { fromLocalInput, localInput } from "./dates";

describe("family timezone", () => {
  it("converts Madrid input independently of the browser timezone", () => {
    expect(fromLocalInput("2026-07-06T09:00", "Europe/Madrid")).toBe(
      "2026-07-06T07:00:00.000Z",
    );
    expect(localInput("2026-01-06T08:00:00Z", "Europe/Madrid")).toBe(
      "2026-01-06T09:00",
    );
  });
  it("rejects the missing or ambiguous hours at daylight saving transitions", () => {
    expect(() => fromLocalInput("2026-03-29T02:30", "Europe/Madrid")).toThrow(
      "no existe",
    );
    expect(() => fromLocalInput("2026-10-25T02:30", "Europe/Madrid")).toThrow(
      "se repite",
    );
  });
});
