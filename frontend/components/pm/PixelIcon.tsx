import type { CSSProperties } from "react";
import { PM_BITMAPS, PM_LOGO_ROWS, type PixelIconName } from "./bitmaps";

function bitmapRects(rows: readonly string[]) {
  const rects: { x: number; y: number }[] = [];
  for (let y = 0; y < rows.length; y++) {
    for (let x = 0; x < rows[y].length; x++) {
      if (rows[y][x] === "#") rects.push({ x, y });
    }
  }
  return rects;
}

// 9×9 bitmap icon rendered as SVG rects — stays crisp at any size.
export function PixelIcon({
  name,
  size = 14,
  color = "currentColor",
  className,
  style,
}: {
  name: PixelIconName;
  size?: number;
  color?: string;
  className?: string;
  style?: CSSProperties;
}) {
  const rows = PM_BITMAPS[name] ?? PM_BITMAPS.box;
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${rows.length} ${rows.length}`}
      fill={color}
      className={className}
      style={{ display: "block", flexShrink: 0, ...style }}
      aria-hidden="true"
      shapeRendering="crispEdges"
    >
      {bitmapRects(rows).map((r) => (
        <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width="1" height="1" />
      ))}
    </svg>
  );
}

// Logo mark: pixel double-chevron in the accent color.
export function PmLogo({ size = 18, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 9 9"
      fill="var(--accent-bright)"
      className={className}
      style={{ display: "block", flexShrink: 0 }}
      aria-hidden="true"
      shapeRendering="crispEdges"
    >
      {bitmapRects(PM_LOGO_ROWS).map((r) => (
        <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width="1" height="1" />
      ))}
    </svg>
  );
}
