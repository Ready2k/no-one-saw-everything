import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

const MAP_WIDTH = 6144;
const MAP_HEIGHT = 4608;
const MANIFEST_URL =
  "/art/town/tiles_3x3_hd/living_town_v2/ambient_sprites/ambient_sprites_manifest.json";
const COHESIVE_MAP_URL =
  "/art/town/tiles_3x3_hd/living_town_v2/cohesive_preview/town_overworld_living_town_v2_fauna_cohesive_preview.jpg";
const REMASTER_TILE_URLS = [
  [
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_A1_living_town_remaster_v5_clean_generated.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_A2_living_town_remaster_v5_clean_generated.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_A3_living_town_remaster_v5_clean_generated.png",
  ],
  [
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_B1_living_town_remaster_v5_clean_generated.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_B2_living_town_remaster_v5_clean_generated.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_B3_living_town_remaster_v5_clean_generated.png",
  ],
  [
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_C1_living_town_remaster_v5_clean_generated.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_C2_living_town_remaster_v5_clean_generated.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/town_overworld_C3_living_town_remaster_v5_clean_generated.png",
  ],
];

const ZOOM_TILE_URLS = [
  [
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v7/town_overworld_A1_living_town_remaster_v5_zoom_interior_v7.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v7/town_overworld_A2_living_town_remaster_v5_zoom_interior_v7.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v7/town_overworld_A3_living_town_remaster_v5_zoom_interior_v7.png",
  ],
  [
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v7/town_overworld_B1_living_town_remaster_v5_zoom_interior_v7.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v8_hobbs_cafe/town_overworld_B2_zoom_interior_v8_hobbs_cafe_edge_locked.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v7/town_overworld_B3_living_town_remaster_v5_zoom_interior_v7.png",
  ],
  [
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v7/town_overworld_C1_living_town_remaster_v5_zoom_interior_v7.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v7/town_overworld_C2_living_town_remaster_v5_zoom_interior_v7.png",
    "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5/zoom_interior_v7/town_overworld_C3_living_town_remaster_v5_zoom_interior_v7.png",
  ],
];

const TILE_URLS = [
  [
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_A1_living_town_v2_fauna.png",
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_A2_living_town_v2_fauna.png",
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_A3_living_town_v2_fauna.png",
  ],
  [
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_B1_living_town_v2_fauna.png",
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_B2_living_town_all_cases_v2_fauna.png",
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_B3_living_town_v2_fauna.png",
  ],
  [
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_C1_living_town_v2_fauna.png",
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_C2_living_town_v2_fauna.png",
    "/art/town/tiles_3x3_hd/living_town_v2/town_overworld_C3_living_town_v2_fauna.png",
  ],
];

interface AmbientPlacement {
  x: number;
  y: number;
  width: number;
  height: number;
  region: string;
}

interface AmbientAsset {
  id: string;
  title: string;
  description: string;
  spritesheet: string;
  frame_width: number;
  frame_height: number;
  frames: number;
  fps: number;
  blend_mode: string;
  default_opacity: number;
  suggested_placements: AmbientPlacement[];
}

interface AmbientManifest {
  assets: AmbientAsset[];
}

interface AmbientInstance {
  key: string;
  asset: AmbientAsset;
  placement: AmbientPlacement;
  delay: number;
}

interface MapLabel {
  id: string;
  title: string;
  x: number;
  y: number;
  w: number;
  h: number;
  tone?: "place" | "civic";
}

const B2_OFFSET_X = 2048;
const B2_OFFSET_Y = 1536;
const TILE_SIZE = 32;

const B2_BUILDING_LABELS: MapLabel[] = [
  { id: "loc_fishery", title: "Fishery", x: 2, y: 8, w: 10, h: 8, tone: "place" },
  { id: "loc_bookshop", title: "Reed & Bell", x: 16, y: 8, w: 10, h: 9, tone: "place" },
  { id: "loc_hobbs_cafe", title: "Hobbs Cafe", x: 27, y: 8, w: 10, h: 8, tone: "place" },
  { id: "loc_marcus_house", title: "Marcus House", x: 39, y: 7, w: 11, h: 9, tone: "place" },
  { id: "loc_nadia_flat", title: "Nadia Flat", x: 54, y: 7, w: 10, h: 9, tone: "place" },
  { id: "loc_pub", title: "Mallet & Crown", x: 8, y: 18, w: 13, h: 11, tone: "place" },
  { id: "loc_clinic", title: "Clinic", x: 45, y: 17, w: 10, h: 9, tone: "place" },
  { id: "loc_owen_house", title: "Owen Yard", x: 53, y: 20, w: 11, h: 12, tone: "place" },
  { id: "loc_ben_flat", title: "Ben Flat", x: 6, y: 35, w: 9, h: 10, tone: "place" },
  { id: "loc_priya_flat", title: "Priya Flat", x: 16, y: 34, w: 10, h: 9, tone: "place" },
  { id: "loc_elias_house", title: "Elias Cottage", x: 28, y: 34, w: 8, h: 9, tone: "place" },
  { id: "loc_solicitors_office", title: "Solicitors", x: 40, y: 35, w: 10, h: 9, tone: "place" },
  { id: "loc_ruth_cottage", title: "Ruth Cottage", x: 52, y: 34, w: 11, h: 10, tone: "place" },
  { id: "loc_village_square", title: "Village Square", x: 22, y: 15, w: 23, h: 16, tone: "civic" },
  { id: "loc_fountain", title: "Fountain", x: 31, y: 21, w: 4, h: 4, tone: "civic" },
  { id: "loc_rear_alley", title: "Rear Alley", x: 28, y: 2, w: 24, h: 7, tone: "civic" },
];

function b2LabelStyle(label: MapLabel): CSSProperties {
  const cx = B2_OFFSET_X + (label.x + label.w / 2) * TILE_SIZE;
  const cy = B2_OFFSET_Y + (label.y + label.h / 2) * TILE_SIZE;
  return {
    left: `${(cx / MAP_WIDTH) * 100}%`,
    top: `${(cy / MAP_HEIGHT) * 100}%`,
  };
}

function spriteMixBlendMode(mode: string): CSSProperties["mixBlendMode"] {
  return mode === "screen" ? "screen" : "normal";
}

function tilePlacementStyle(rowIndex: number, colIndex: number): CSSProperties {
  return {
    left: `calc(${(colIndex / 3) * 100}% - ${colIndex > 0 ? 0.5 : 0}px)`,
    top: `calc(${(rowIndex / 3) * 100}% - ${rowIndex > 0 ? 0.5 : 0}px)`,
    width: `calc(${100 / 3}% + 1px)`,
    height: `calc(${100 / 3}% + 1px)`,
  };
}

export default function AmbientTownPreview() {
  const [manifest, setManifest] = useState<AmbientManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [buildingLabels, setBuildingLabels] = useState(true);
  const [ambientLabels, setAmbientLabels] = useState(false);
  const [mood, setMood] = useState<"day" | "dusk" | "mist" | "night">("dusk");
  const [mapSource, setMapSource] = useState<"remaster" | "zoom" | "cohesive" | "raw">("zoom");

  useEffect(() => {
    fetch(MANIFEST_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
      })
      .then(setManifest)
      .catch((e) => setError(String(e)));
  }, []);

  const instances = useMemo<AmbientInstance[]>(() => {
    return (manifest?.assets ?? []).flatMap((asset, assetIndex) =>
      asset.suggested_placements.map((placement, placementIndex) => ({
        key: `${asset.id}-${placementIndex}`,
        asset,
        placement,
        delay: -((assetIndex * 0.37 + placementIndex * 0.61) % 2.8),
      }))
    );
  }, [manifest]);

  return (
    <div className={`ambient-town-page mood-${mood}`}>
      <header className="ambient-town-header">
        <div>
          <p className="eyebrow">Living Town V2</p>
          <h1>Ambient Map Preview</h1>
        </div>
        <div className="ambient-town-controls" aria-label="Ambient preview controls">
          <div className="segmented" role="group" aria-label="Mood">
            {(["day", "dusk", "mist", "night"] as const).map((id) => (
              <button
                key={id}
                type="button"
                className={mood === id ? "active" : ""}
                onClick={() => setMood(id)}
              >
                {id}
              </button>
            ))}
          </div>
          <div className="segmented" role="group" aria-label="Map source">
            {(["remaster", "zoom", "cohesive", "raw"] as const).map((id) => (
              <button
                key={id}
                type="button"
                className={mapSource === id ? "active" : ""}
                onClick={() => setMapSource(id)}
              >
                {id}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => setPaused((v) => !v)}>
            {paused ? "Play" : "Pause"}
          </button>
          <button
            type="button"
            className={buildingLabels ? "active" : ""}
            onClick={() => setBuildingLabels((v) => !v)}
          >
            {buildingLabels ? "Hide buildings" : "Show buildings"}
          </button>
          <button
            type="button"
            className={ambientLabels ? "active" : ""}
            onClick={() => setAmbientLabels((v) => !v)}
          >
            {ambientLabels ? "Hide sprites" : "Show sprites"}
          </button>
        </div>
      </header>

      <main className="ambient-town-shell">
        <section className="ambient-town-map-wrap" aria-label="Animated living town map">
          <div className="ambient-town-map" style={{ aspectRatio: `${MAP_WIDTH} / ${MAP_HEIGHT}` }}>
            {mapSource === "remaster" || mapSource === "zoom" ? (
              <div className="ambient-town-tiles" aria-hidden="true">
                {(mapSource === "zoom" ? ZOOM_TILE_URLS : REMASTER_TILE_URLS).map((row, rowIndex) =>
                  row.map((url, colIndex) => (
                    <img
                      key={url}
                      src={url}
                      alt=""
                      draggable={false}
                      style={tilePlacementStyle(rowIndex, colIndex)}
                    />
                  ))
                )}
              </div>
            ) : mapSource === "cohesive" ? (
              <img
                className="ambient-town-cohesive-image"
                src={COHESIVE_MAP_URL}
                alt=""
                draggable={false}
                aria-hidden="true"
              />
            ) : (
              <div className="ambient-town-tiles" aria-hidden="true">
                {TILE_URLS.map((row, rowIndex) =>
                  row.map((url, colIndex) => (
                    <img
                      key={url}
                      src={url}
                      alt=""
                      draggable={false}
                      style={tilePlacementStyle(rowIndex, colIndex)}
                    />
                  ))
                )}
              </div>
            )}
            <div className="ambient-town-tint" aria-hidden="true" />
            <div className={`ambient-town-sprites ${paused ? "paused" : ""}`} aria-hidden="true">
              {instances.map(({ key, asset, placement, delay }) => (
                <div
                  key={key}
                  className={`ambient-sprite ambient-sprite-${asset.id}`}
                  title={`${asset.title}: ${placement.region}`}
                  style={
                    {
                      left: `${(placement.x / MAP_WIDTH) * 100}%`,
                      top: `${(placement.y / MAP_HEIGHT) * 100}%`,
                      width: `${(placement.width / MAP_WIDTH) * 100}%`,
                      height: `${(placement.height / MAP_HEIGHT) * 100}%`,
                      backgroundImage: `url(${asset.spritesheet})`,
                      animationDuration: `${asset.frames / asset.fps}s`,
                      animationDelay: `${delay}s`,
                      animationTimingFunction: `steps(${asset.frames})`,
                      opacity: asset.default_opacity,
                      mixBlendMode: spriteMixBlendMode(asset.blend_mode),
                      "--sprite-frames": asset.frames,
                    } as CSSProperties
                  }
                />
              ))}
            </div>
            {buildingLabels && (
              <div className="ambient-town-building-labels" aria-hidden="true">
                {B2_BUILDING_LABELS.map((label) => (
                  <span
                    key={label.id}
                    className={label.tone === "civic" ? "civic" : undefined}
                    style={b2LabelStyle(label)}
                  >
                    {label.title}
                  </span>
                ))}
              </div>
            )}
            {ambientLabels && (
              <div className="ambient-town-labels ambient-effect-labels" aria-hidden="true">
                {instances.map(({ key, asset, placement }) => (
                  <span
                    key={`label-${key}`}
                    style={{
                      left: `${((placement.x + placement.width / 2) / MAP_WIDTH) * 100}%`,
                      top: `${((placement.y + placement.height) / MAP_HEIGHT) * 100}%`,
                    }}
                  >
                    {asset.title}
                  </span>
                ))}
              </div>
            )}
          </div>
        </section>
        <aside className="ambient-town-panel">
          {error && <p className="muted">Could not load ambient manifest: {error}</p>}
          {!manifest && !error && <p className="muted">Loading ambient sprites...</p>}
          {manifest && (
            <>
              <p className="ambient-town-count">{instances.length} ambient placements</p>
              {manifest.assets.map((asset) => (
                <div className="ambient-town-asset" key={asset.id}>
                  <strong>{asset.title}</strong>
                  <span>{asset.suggested_placements.length} placements</span>
                </div>
              ))}
            </>
          )}
        </aside>
      </main>
    </div>
  );
}
