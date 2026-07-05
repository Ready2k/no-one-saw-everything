import { useState, useRef, useEffect } from "react";
import type { MapBounds, ClueHotspot } from "../types";

export function MagnifyingSearch({
  bounds,
  hiddenClues,
  imageUrl = "/map/the_ville.png",
  spriteAsset,
  isPortrait = false,
  onDiscover,
}: {
  bounds: MapBounds | null;
  hiddenClues: ClueHotspot[];
  imageUrl?: string;
  spriteAsset?: string;
  isPortrait?: boolean;
  onDiscover: (clueId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [activeHotspot, setActiveHotspot] = useState<ClueHotspot | null>(null);
  const [dim, setDim] = useState({ w: 0, h: 0 });
  const [zoomLevel, setZoomLevel] = useState(1); // 1x to 3x

  const ZOOM = 2.5;
  const LENS_SIZE = 140 / zoomLevel;

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      setDim({
        w: entries[0].contentRect.width,
        h: entries[0].contentRect.height,
      });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const MAP_W = isPortrait ? 512 : 719;
  const MAP_H = isPortrait ? 512 : 513;

  const safeBounds = bounds || { x: 0, y: 0, width: MAP_W, height: MAP_H };

  // Reduce the view window to zoom in on the map
  const VIEW_W = (isPortrait ? MAP_W : 240) / zoomLevel;
  const VIEW_H = (isPortrait ? MAP_H : 160) / zoomLevel;

  const cx = safeBounds.x + safeBounds.width / 2;
  const cy = safeBounds.y + safeBounds.height / 2;

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

    const pctX = (x / dim.w) * 100;
    const pctY = (y / dim.h) * 100;

    const found = adjustedClues.find((c) => {
      const dx = c.x - pctX;
      const dy = (c.y - pctY) / (dim.w / dim.h);
      const dist = Math.sqrt(dx * dx + dy * dy);
      return dist <= c.radius;
    });
    setActiveHotspot(found || null);
  };

  const handleMouseLeave = () => {
    setMousePos(null);
    setActiveHotspot(null);
  };

  const handleClick = () => {
    if (activeHotspot) {
      onDiscover(activeHotspot.clue_id);
    }
  };
  
  return (
    <div
      ref={containerRef}
      className={`magnifying-container ${activeHotspot ? "hotspot-active" : ""}`}
      style={{ paddingBottom: `${(1 / aspectRatio) * 100}%` }}
      onMouseMove={handleMouseMove}
      onTouchMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onTouchEnd={handleMouseLeave}
      onClick={handleClick}
    >
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
          {spriteAsset ? (
            <div style={{
              width: "100%",
              height: "100%",
              backgroundImage: `url('/map/sprites/${spriteAsset}')`,
              backgroundSize: isPortrait ? "300% 400%" : "contain",
              backgroundPosition: isPortrait ? "50% 0%" : "center",
              backgroundRepeat: "no-repeat",
              imageRendering: "pixelated",
              backgroundColor: isPortrait ? "#2a2a2a" : "transparent",
              ...(isPortrait && { filter: "grayscale(80%) brightness(0.6) sepia(20%) hue-rotate(180deg)" })
            }} />
          ) : (
            <img 
              src={imageUrl} 
              alt="Map area"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                e.currentTarget.parentElement!.style.backgroundColor = "#2a2a2a";
              }}
              style={{
                 width: "100%",
                 height: "100%",
                 imageRendering: "pixelated",
                 ...(isPortrait && { filter: "grayscale(80%) brightness(0.6) sepia(20%) hue-rotate(180deg)", objectFit: "cover" })
              }} 
            />
          )}
          {isPortrait && <div className="deceased-xs">X&nbsp;&nbsp;X</div>}
        </div>
      </div>

      {adjustedClues.map(c => {
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
                        {spriteAsset ? (
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
                            src={imageUrl} 
                            alt=""
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                              e.currentTarget.parentElement!.style.backgroundColor = "#2a2a2a";
                            }}
                            style={{
                               width: "100%",
                               height: "100%",
                               imageRendering: "pixelated",
                               ...(isPortrait && { filter: "grayscale(80%) brightness(0.6) sepia(20%) hue-rotate(180deg)", objectFit: "cover" })
                            }} 
                          />
                        )}
                        {isPortrait && <div className="deceased-xs">X&nbsp;&nbsp;X</div>}
                      </div>
                    </div>
                 </div>
              </div>
           </div>
           <div className="lens-glass"></div>
           <div className="lens-handle"></div>
        </div>
      )}
    </div>
  );
}
