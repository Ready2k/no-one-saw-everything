import { describe, it, expect } from "vitest";
import { demeanourFor } from "./demeanour";

describe("demeanourFor", () => {
  it("reads composure as the inverse of pressure", () => {
    expect(demeanourFor(0).composure).toBe(100);
    expect(demeanourFor(0.5).composure).toBe(50);
    expect(demeanourFor(1).composure).toBe(0);
  });

  it("moves through the full range, not just one threshold", () => {
    // The bug this replaces: the old label only changed once, at 0.3.
    const labels = [0, 0.2, 0.45, 0.7, 0.95].map((p) => demeanourFor(p).label);
    expect(new Set(labels).size).toBe(5);
    expect(labels).toEqual(["Composed", "Guarded", "Rattled", "Cornered", "Breaking"]);
  });

  it("moves off Composed when the first authored deflect (+0.10) lands", () => {
    // The challenge UI says "their composure slips" for any positive delta; the hint must not
    // still claim nothing has touched them.
    expect(demeanourFor(0.1).label).toBe("Guarded");
    expect(demeanourFor(0.05).label).toBe("Composed"); // the related-evidence nudge stays quiet
  });

  it("lets a fresh emotional beat override the steady-state read for a turn", () => {
    // A self-contradiction is only +0.3 pressure, but the player should see it as flustered now.
    expect(demeanourFor(0.2, "floundering").label).toBe("Floundering");
    expect(demeanourFor(0.5, "broken").label).toBe("Breaking");
  });

  it("clamps out-of-range pressure", () => {
    expect(demeanourFor(-1).composure).toBe(100);
    expect(demeanourFor(2).composure).toBe(0);
  });
});
