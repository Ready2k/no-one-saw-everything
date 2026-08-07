import { describe, expect, it } from "vitest";
import { sceneArtFor } from "./sceneArt";

describe("intro and investigation scene artwork", () => {
  it.each([
    ["case_001", "loc_cafe_storage", "/art/case_001/storage_room_interactive_wide_v1.avif"],
    ["case_002", "loc_bookshop", "/art/case_002/reed_bell_bookshop_sunset_investigation_v1.avif"],
    ["case_003", "loc_village_square", "/art/case_003/village_square_afternoon_investigation_v2.avif"],
    ["case_004", "loc_village_square", "/art/case_004/village_square_midnight_investigation_v2.avif"],
    ["case_005", "loc_rear_alley", "/art/case_005/rear_alley_after_fire_investigation_v2.avif"],
    ["case_006", "loc_marcus_house", "/art/case_001/marcus_house_investigation_v4.avif"],
    ["case_007", "loc_bookshop_back", "/art/case_001/bookshop_back_room_investigation_v2.avif"],
    ["case_010", "loc_cafe_storage", "/art/case_010/cafe_storage_dawn_hd.avif"],
  ])("resolves %s discovery artwork through the canonical scene library", (caseId, locationId, expected) => {
    expect(sceneArtFor(caseId, locationId, "/art/rejected/stale.png")).toBe(expected);
  });

  it("does not let authored legacy art override a recurring location identity", () => {
    expect(sceneArtFor("case_007", "loc_rear_alley", "/art/case_007/rewind/grey_coat_alley_hd.avif"))
      .toBe("/art/case_007/rear_alley_fair_evening_v1.avif");
    expect(sceneArtFor("case_004", "loc_owen_house", "/art/town/places_hd/village_square_hd.avif"))
      .toBe("/art/case_004/owen_house_yard_midnight_investigation_v1.avif");
  });

  it.each([
    "loc_village_square",
    "loc_fountain",
    "loc_elias_bench",
    "loc_bookshop",
    "loc_bookshop_back",
    "loc_rear_alley",
    "loc_hobbs_cafe",
    "loc_clinic",
    "loc_owen_house",
    "loc_priya_flat",
  ])("keeps every Case 2 place in its sunset artwork set: %s", (locationId) => {
    expect(sceneArtFor("case_002", locationId)).toMatch(/^\/art\/case_002\/.+_sunset_investigation_v1\.png$/);
  });

  it("uses the existing case-specific dawn sets instead of neutral fallbacks", () => {
    expect(sceneArtFor("case_005", "loc_hobbs_cafe")).toBe("/art/case_005/hobbs_cafe_dawn_hd.avif");
    expect(sceneArtFor("case_005", "loc_owen_house")).toBe("/art/case_005/owen_yard_dawn_hd.avif");
    expect(sceneArtFor("case_010", "loc_clinic")).toBe("/art/case_010/clinic_dawn_hd.avif");
    expect(sceneArtFor("case_010", "loc_rear_alley")).toBe("/art/case_010/rear_alley_fire_hd.avif");
  });

  it("uses time-matched art for the completed afternoon and midnight sets", () => {
    expect(sceneArtFor("case_003", "loc_clinic_dispensary"))
      .toBe("/art/case_003/clinic_dispensary_late_afternoon_investigation_v1.avif");
    expect(sceneArtFor("case_003", "loc_elias_bench"))
      .toBe("/art/case_002/elias_bench_sunset_investigation_v1.avif");
    expect(sceneArtFor("case_004", "loc_pub"))
      .toBe("/art/case_004/mallet_crown_pub_midnight_investigation_v1.avif");
    expect(sceneArtFor("case_004", "loc_priya_flat"))
      .toBe("/art/case_004/priya_flat_midnight_investigation_v1.avif");
  });

  it("uses explicit discovery-dawn and lantern-fair sets for Cases 6 and 7", () => {
    expect(sceneArtFor("case_006", "loc_village_square")).toBe("/art/case_005/village_square_dawn_hd.avif");
    expect(sceneArtFor("case_006", "loc_bookshop")).toBe("/art/case_005/bookshop_dawn_hd.avif");
    expect(sceneArtFor("case_007", "loc_village_square"))
      .toBe("/art/case_007/village_square_lantern_fair_evening_v1.avif");
    expect(sceneArtFor("case_007", "loc_fountain"))
      .toBe("/art/case_007/fountain_lantern_fair_evening_v1.avif");
  });
});
