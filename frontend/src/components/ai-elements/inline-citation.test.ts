import { describe, expect, it } from "vitest";
import { canOpenDocument } from "@/components/ai-elements/citation-utils";
import type { DocumentCitationSource } from "@/components/ai-elements/inline-citation";

function source(
  overrides: Partial<DocumentCitationSource> = {},
): DocumentCitationSource {
  return {
    type: "source-document",
    sourceId: "source-1",
    fileId: "file-1",
    filename: "document.pdf",
    mediaType: "application/pdf",
    page: 1,
    anchor: "p1-1",
    bbox: [0.1, 0.2, 0.8, 0.3],
    collectionId: "collection-1",
    ...overrides,
  };
}

describe("canOpenDocument", () => {
  it("opens PDF citations with a page and bounding box", () => {
    expect(canOpenDocument(source())).toBe(true);
  });

  it("opens page-less prose citations in the resource viewer", () => {
    expect(canOpenDocument(source({ page: null, bbox: null }))).toBe(true);
  });

  it("opens tabular resources in the resource viewer", () => {
    expect(
      canOpenDocument(
        source({
          filename: "employees.csv",
          mediaType: "text/csv",
          page: null,
          bbox: null,
        }),
      ),
    ).toBe(true);
  });
});
