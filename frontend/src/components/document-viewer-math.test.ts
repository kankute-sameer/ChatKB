import { describe, expect, it } from "vitest";
import { calculateOverlay } from "@/components/document-viewer-math";

describe("calculateOverlay", () => {
  it("scales normalized top-left coordinates to rendered pixels", () => {
    expect(calculateOverlay([0.1, 0.2, 0.6, 0.5], 800, 1000)).toEqual({
      left: 80,
      top: 200,
      width: 400,
      height: 300,
    });
  });

  it("rejects malformed bounding boxes", () => {
    expect(calculateOverlay([0.1, 0.2], 800, 1000)).toBeNull();
  });
});
