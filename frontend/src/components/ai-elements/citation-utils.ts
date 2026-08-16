import type { DocumentCitationSource } from "@/components/ai-elements/inline-citation";

export function canOpenDocument(source: DocumentCitationSource): boolean {
  return Boolean(source.fileId);
}
