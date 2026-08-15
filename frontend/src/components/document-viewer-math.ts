export interface OverlayRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function calculateOverlay(
  bbox: readonly number[],
  renderedWidth: number,
  renderedHeight: number,
): OverlayRect | null {
  if (bbox.length !== 4) return null;
  const [left, top, right, bottom] = bbox;
  if (
    left == null ||
    top == null ||
    right == null ||
    bottom == null ||
    ![left, top, right, bottom].every(Number.isFinite)
  ) {
    return null;
  }
  return {
    left: left * renderedWidth,
    top: top * renderedHeight,
    width: Math.max(0, right - left) * renderedWidth,
    height: Math.max(0, bottom - top) * renderedHeight,
  };
}
