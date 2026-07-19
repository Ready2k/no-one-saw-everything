import { useState, useRef, useEffect } from "react";
import type { MapBounds, ClueHotspot } from "../types";

function getClueEmoji(title: string): string {
  const t = title.toLowerCase();
  if (t.includes("blood") || t.includes("wound") || t.includes("laceration") || t.includes("cut")) return "🩸";
  if (t.includes("glass") || t.includes("shatter")) return "🪟";
  if (t.includes("footprint") || t.includes("shoe") || t.includes("boot") || t.includes("mud")) return "👣";
  if (t.includes("note") || t.includes("letter") || t.includes("paper") || t.includes("receipt") || t.includes("ledger") || t.includes("document")) return "📄";
  if (t.includes("knife") || t.includes("blade") || t.includes("weapon") || t.includes("stab")) return "🔪";
  if (t.includes("key")) return "🔑";
  if (t.includes("gun") || t.includes("pistol") || t.includes("bullet") || t.includes("casing")) return "🔫";
  if (t.includes("hair")) return "🧬";
  if (t.includes("cloth") || t.includes("fabric") || t.includes("fiber") || t.includes("shirt") || t.includes("pocket")) return "👕";
  if (t.includes("ring") || t.includes("jewelry") || t.includes("necklace") || t.includes("watch") || t.includes("time")) return "⌚";
  if (t.includes("wallet") || t.includes("purse")) return "👛";
  if (t.includes("money") || t.includes("cash") || t.includes("coin") || t.includes("till")) return "💰";
  if (t.includes("bottle") || t.includes("vial") || t.includes("poison") || t.includes("liquid") || t.includes("drink")) return "🍾";
  if (t.includes("phone") || t.includes("device")) return "📱";
  if (t.includes("cig") || t.includes("ash")) return "🚬";
  if (t.includes("match") || t.includes("lighter") || t.includes("burn") || t.includes("fire")) return "🔥";
  if (t.includes("photo") || t.includes("picture") || t.includes("camera")) return "📸";
  if (t.includes("dirt") || t.includes("soil")) return "🟤";
  if (t.includes("weight") || t.includes("brass") || t.includes("metal") || t.includes("heavy") || t.includes("statue")) return "🗿";
  if (t.includes("pill") || t.includes("drug") || t.includes("meds")) return "💊";
  if (t.includes("rope") || t.includes("wire") || t.includes("cord") || t.includes("strangle") || t.includes("tie")) return "🪢";
  if (t.includes("book") || t.includes("journal") || t.includes("diary")) return "📓";
  if (t.includes("fingerprint") || t.includes("print") || t.includes("smudge")) return "👆";
  return "✨";
}

export function MagnifyingSearch({
  bounds,
  hiddenClues,
  imageUrl = "/map/the_ville.png",
  mapWidth = 719,
  mapHeight = 513,
  spriteAsset,
  isIllustration = false,
  isPortrait = false,
  sheetFolded = true,
  onDiscover,
}: {
  bounds: MapBounds | null;
  hiddenClues: ClueHotspot[];
  imageUrl?: string;
  mapWidth?: number;
  mapHeight?: number;
  spriteAsset?: string;
  isIllustration?: boolean;
  isPortrait?: boolean;
  /** Body exam only: while the morgue sheet covers the subject, nothing can be found. */
  sheetFolded?: boolean;
  onDiscover: (clueId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [activeHotspot, setActiveHotspot] = useState<ClueHotspot | null>(null);
  const [dim, setDim] = useState({ w: 0, h: 0 });
  const [zoomLevel, setZoomLevel] = useState(1); // 1x to 3x
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });

  const isDragging = useRef(false);
  const lastClientPos = useRef<{x: number, y: number} | null>(null);
  const dragDist = useRef(0);
  const imageClassName = [
    isIllustration ? "place-search-image fountain-lit" : "",
    isPortrait ? "post-mortem-portrait" : "",
  ].filter(Boolean).join(" ");
  const imageRendering = isIllustration || isPortrait ? "auto" : "pixelated";
  const useSpritePortrait = isPortrait && spriteAsset && !imageUrl;

  const ZOOM = 2.5;
  // Lens scales with the search area so it reads as a hand magnifier over the
  // subject rather than a fixed-size overlay.
  const LENS_SIZE = isPortrait
    ? (Math.min(40, Math.max(28, dim.w * 0.09)) / Math.min(zoomLevel, 1.5))
    : (Math.min(90, Math.max(50, dim.w * 0.16)) / Math.min(zoomLevel, 1.5));

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      setDim({
        w: entries[0].contentRect.width,
        h: containerRef.current!.getBoundingClientRect().height,
      });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const MAP_W = isPortrait ? 512 : mapWidth;
  const MAP_H = isPortrait ? 512 : mapHeight;

  const safeBounds = bounds || { x: 0, y: 0, width: MAP_W, height: MAP_H };

  // Reduce the view window to zoom in on the map
  // The normal map uses a 240×160 investigation window, but an authored
  // illustration can be a compact 0–100 scene. Never ask the crop to show a
  // viewport larger than the source image, or it will shrink into one corner.
  const VIEW_W = (isPortrait ? MAP_W : Math.min(240, MAP_W)) / zoomLevel;
  const VIEW_H = (isPortrait ? MAP_H : Math.min(160, MAP_H)) / zoomLevel;

  const cx = safeBounds.x + safeBounds.width / 2 + panOffset.x;
  const cy = safeBounds.y + safeBounds.height / 2 + panOffset.y;

  let padX = cx - VIEW_W / 2;
  let padY = cy - VIEW_H / 2;

  padX = Math.max(0, Math.min(MAP_W - VIEW_W, padX));
  padY = Math.max(0, Math.min(MAP_H - VIEW_H, padY));

  const paddedBounds = { x: padX, y: padY, width: VIEW_W, height: VIEW_H };

  const aspectRatio = paddedBounds.width / paddedBounds.height;
  const bgSizeX = (MAP_W / paddedBounds.width) * 100;
  const bgSizeY = (MAP_H / paddedBounds.height) * 100;
  const bgTransX = (paddedBounds.x / MAP_W) * 100;
  const bgTransY = (paddedBounds.y / MAP_H) * 100;

  const adjustedClues = hiddenClues.map(c => {
    const absX = safeBounds.x + (c.x / 100) * safeBounds.width;
    const absY = safeBounds.y + (c.y / 100) * safeBounds.height;
    const newPctX = ((absX - paddedBounds.x) / paddedBounds.width) * 100;
    const newPctY = ((absY - paddedBounds.y) / paddedBounds.height) * 100;
    const absRadius = (c.radius / 100) * safeBounds.width;
    const newPctRadius = (absRadius / paddedBounds.width) * 100;
    return { ...c, x: newPctX, y: newPctY, radius: newPctRadius };
  });

  const handlePointerDown = (e: React.MouseEvent | React.TouchEvent) => {
    isDragging.current = true;
    dragDist.current = 0;
    let clientX, clientY;
    if ("touches" in e) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = (e as React.MouseEvent).clientX;
      clientY = (e as React.MouseEvent).clientY;
    }
    lastClientPos.current = { x: clientX, y: clientY };
  };

  const handlePointerUp = () => {
    isDragging.current = false;
    lastClientPos.current = null;
  };

  const handleMouseMove = (e: React.MouseEvent | React.TouchEvent) => {
    if (!containerRef.current || dim.w === 0) return;
    const rect = containerRef.current.getBoundingClientRect();
    
    let clientX, clientY;
    if ("touches" in e) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = (e as React.MouseEvent).clientX;
      clientY = (e as React.MouseEvent).clientY;
    }
    
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    setMousePos({ x, y });

    if (isDragging.current && lastClientPos.current) {
      const dx = clientX - lastClientPos.current.x;
      const dy = clientY - lastClientPos.current.y;
      dragDist.current += Math.sqrt(dx * dx + dy * dy);
      
      const mapDx = dx * (VIEW_W / dim.w);
      const mapDy = dy * (VIEW_H / dim.h);

      setPanOffset(prev => {
        let nx = prev.x - mapDx;
        let ny = prev.y - mapDy;

        const center_x = safeBounds.x + safeBounds.width / 2;
        const center_y = safeBounds.y + safeBounds.height / 2;

        const min_nx = VIEW_W / 2 - center_x;
        const max_nx = MAP_W - VIEW_W / 2 - center_x;

        const min_ny = VIEW_H / 2 - center_y;
        const max_ny = MAP_H - VIEW_H / 2 - center_y;

        nx = Math.max(min_nx, Math.min(max_nx, nx));
        ny = Math.max(min_ny, Math.min(max_ny, ny));

        return { x: nx, y: ny };
      });
      lastClientPos.current = { x: clientX, y: clientY };
    }

    const pctX = (x / dim.w) * 100;
    const pctY = (y / dim.h) * 100;

    const lensRadiusPct = ((LENS_SIZE / 2) / dim.w) * 100;

    if (isPortrait && !sheetFolded) {
      setActiveHotspot(null);
      return;
    }

    const found = adjustedClues.find((c) => {
      const dx = c.x - pctX;
      const aspectRatio = dim.h > 0 ? dim.w / dim.h : 1;
      const dy = (c.y - pctY) / aspectRatio;
      const dist = Math.sqrt(dx * dx + dy * dy);
      
      // The lens must be relatively sized to the clue to find it.
      // A leniency of 1.25x means small clues (e.g. 4%) require ~2.5x or 3x zoom.
      const isRelativeSize = lensRadiusPct <= c.radius * 1.25;

      return dist <= c.radius && isRelativeSize;
    });
    setActiveHotspot(found || null);
  };

  const handleMouseLeave = () => {
    setMousePos(null);
    setActiveHotspot(null);
    isDragging.current = false;
    lastClientPos.current = null;
  };

  const handleClick = () => {
    if (dragDist.current > 5) {
      return;
    }
    if (activeHotspot) {
      onDiscover(activeHotspot.clue_id);
    }
  };

  const pan = (dx: number, dy: number) => {
    const step = 80 / zoomLevel;
    setPanOffset(prev => {
      let nx = prev.x + dx * step;
      let ny = prev.y + dy * step;

      const center_x = safeBounds.x + safeBounds.width / 2;
      const center_y = safeBounds.y + safeBounds.height / 2;

      const min_nx = VIEW_W / 2 - center_x;
      const max_nx = MAP_W - VIEW_W / 2 - center_x;

      const min_ny = VIEW_H / 2 - center_y;
      const max_ny = MAP_H - VIEW_H / 2 - center_y;

      nx = Math.max(min_nx, Math.min(max_nx, nx));
      ny = Math.max(min_ny, Math.min(max_ny, ny));

      return { x: nx, y: ny };
    });
  };
  
  return (
    <div
      ref={containerRef}
      className={`magnifying-container ${activeHotspot ? "hotspot-active" : ""}`}
      style={{ paddingBottom: `${(1 / aspectRatio) * 100}%` }}
      onMouseMove={handleMouseMove}
      onTouchMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onTouchEnd={() => { handleMouseLeave(); handlePointerUp(); }}
      onMouseDown={handlePointerDown}
      onTouchStart={handlePointerDown}
      onMouseUp={handlePointerUp}
      onClick={handleClick}
    >
      {!isPortrait && (
        <>
          <div className="pan-controls" style={{
            position: "absolute", top: 10, left: 10, zIndex: 20,
            display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4,
            background: "rgba(0,0,0,0.6)", padding: 4, borderRadius: 6, border: "1px solid rgba(255,255,255,0.2)"
          }}>
            <div />
            <button className="pan-btn" onClick={(e) => { e.stopPropagation(); pan(0, -1); }}>↑</button>
            <div />
            <button className="pan-btn" onClick={(e) => { e.stopPropagation(); pan(-1, 0); }}>←</button>
            <button className="pan-btn" onClick={(e) => { e.stopPropagation(); setPanOffset({x:0, y:0}); }}>◎</button>
            <button className="pan-btn" onClick={(e) => { e.stopPropagation(); pan(1, 0); }}>→</button>
            <div />
            <button className="pan-btn" onClick={(e) => { e.stopPropagation(); pan(0, 1); }}>↓</button>
            <div />
          </div>

          <div className="zoom-controls">
            <button
              onClick={(e) => { e.stopPropagation(); setZoomLevel(Math.max(1, zoomLevel - 0.5)); }}
              disabled={zoomLevel <= 1}
            >
              -
            </button>
            <div className="zoom-level">{zoomLevel.toFixed(1)}x</div>
            <button
              onClick={(e) => { e.stopPropagation(); setZoomLevel(Math.min(3, zoomLevel + 0.5)); }}
              disabled={zoomLevel >= 3}
            >
              +
            </button>
          </div>
        </>
      )}

      <div className={`magnifying-crop ${isPortrait ? "deceased-portrait" : ""}`}>
        <div style={{
           width: `${bgSizeX}%`,
           height: `${bgSizeY}%`,
           transform: `translate(-${bgTransX}%, -${bgTransY}%)`,
           transformOrigin: "top left",
           position: "absolute",
           top: 0,
           left: 0
        }}>
          {useSpritePortrait ? (
            <div style={{
              width: "100%",
              height: "100%",
              backgroundImage: `url('/map/sprites/${spriteAsset}')`,
              backgroundSize: isPortrait ? "300% 400%" : "contain",
              backgroundPosition: isPortrait ? "50% 0%" : "center",
              backgroundRepeat: "no-repeat",
              imageRendering: "pixelated",
              ...(isPortrait && { filter: "grayscale(80%) brightness(0.6) sepia(20%) hue-rotate(180deg)" })
            }} />
          ) : (
            <img
              className={imageClassName}
              src={imageUrl}
              alt="Map area"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                e.currentTarget.parentElement!.style.backgroundColor = "#2a2a2a";
              }}
              style={{
                 width: "100%",
                 height: "100%",
                 imageRendering,
                 ...(isPortrait && { filter: "grayscale(80%) brightness(0.6) sepia(20%) hue-rotate(180deg)", objectFit: "cover" })
              }}
            />
          )}
          {isPortrait && (
            <div className={`morgue-sheet ${sheetFolded ? "folded" : ""}`} aria-hidden="true" />
          )}
        </div>
      </div>

      {(!isPortrait || sheetFolded) && adjustedClues.map(c => {
         const isActive = activeHotspot?.clue_id === c.clue_id;
         return (
           <div 
             key={c.clue_id}
             className={`hotspot-hint ${isActive ? "active" : ""}`}
             style={{
               left: `${c.x}%`,
               top: `${c.y}%`,
             }}
           />
         )
      })}

      {mousePos && dim.w > 0 && (
        <div
          className="magnifying-lens"
          style={{
            left: mousePos.x,
            top: mousePos.y,
            width: LENS_SIZE,
            height: LENS_SIZE,
            transform: "translate(-50%, -50%)",
          }}
        >
           <div className="lens-content">
              <div
                style={{
                  position: "absolute",
                  left: LENS_SIZE / 2,
                  top: LENS_SIZE / 2,
                }}
              >
                 <div
                    style={{
                      transform: `translate(${-mousePos.x * ZOOM}px, ${-mousePos.y * ZOOM}px)`,
                      width: dim.w * ZOOM,
                      height: dim.h * ZOOM,
                    }}
                 >
                    <div className={`magnifying-crop ${isPortrait ? "deceased-portrait" : ""}`}>
                      <div style={{
                         width: `${bgSizeX}%`,
                         height: `${bgSizeY}%`,
                         transform: `translate(-${bgTransX}%, -${bgTransY}%)`,
                         transformOrigin: "top left",
                         position: "absolute",
                         top: 0,
                         left: 0
                      }}>
                        {useSpritePortrait ? (
                          <div style={{
                            width: "100%",
                            height: "100%",
                            backgroundImage: `url(/map/sprites/${spriteAsset})`,
                            backgroundSize: "300% 400%",
                            backgroundPosition: "50% 0%",
                            backgroundRepeat: "no-repeat",
                            imageRendering: "pixelated",
                            ...(isPortrait && { filter: "grayscale(80%) brightness(0.6) sepia(20%) hue-rotate(180deg)" })
                          }} />
                        ) : (
                          <img 
                            className={imageClassName}
                            src={imageUrl} 
                            alt=""
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                              e.currentTarget.parentElement!.style.backgroundColor = "#2a2a2a";
                            }}
                            style={{
                               width: "100%",
                               height: "100%",
                               imageRendering,
                               ...(isPortrait && { filter: "grayscale(80%) brightness(0.6) sepia(20%) hue-rotate(180deg)", objectFit: "cover" })
                            }}
                          />
                        )}
                        {isPortrait && (
                          <div
                            className={`morgue-sheet ${sheetFolded ? "folded" : ""}`}
                            aria-hidden="true"
                          />
                        )}
                      </div>
                    </div>
                 </div>
              </div>
           </div>
           <div className="lens-glass"></div>
           {activeHotspot && (
             <div 
               key={activeHotspot.clue_id}
               className="emoji-pop"
               style={{
                 position: "absolute",
                 top: "50%",
                 left: "50%",
                 transform: "translate(-50%, -50%)",
                 fontSize: isPortrait ? "32px" : "48px",
                 textShadow: "0px 0px 15px rgba(255,215,0,0.8), 0px 0px 8px rgba(0,0,0,0.9)",
                 zIndex: 2,
                 pointerEvents: "none"
               }}
             >
               {getClueEmoji(activeHotspot.title)}
             </div>
           )}
           <div className="lens-handle"></div>
        </div>
      )}
    </div>
  );
}
