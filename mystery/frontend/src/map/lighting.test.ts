import { describe, expect, it } from "vitest";
import { lightingTint } from "./lighting";

describe("Map Replay timeline lighting", () => {
  it.each([
    [0, "rgb(35, 38, 70)"],
    [390, "rgb(150, 120, 140)"],
    [480, "rgb(235, 215, 195)"],
    [720, "rgb(255, 255, 250)"],
    [900, "rgb(255, 238, 205)"],
    [1050, "rgb(255, 185, 130)"],
    [1170, "rgb(190, 110, 105)"],
    [1260, "rgb(80, 65, 110)"],
  ])("uses the authored tint at minute %i", (minute, expected) => {
    expect(lightingTint(minute)).toBe(expected);
  });

  it("wraps replay times safely across midnight", () => {
    expect(lightingTint(1440)).toBe(lightingTint(0));
    expect(lightingTint(-1)).toBe(lightingTint(1439));
  });
});
