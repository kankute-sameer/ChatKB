import { api } from "@/lib/api";

export type Visibility = "personal" | "workspace";
export type FileStatus = "processing" | "ready" | "failed";

export interface Collection {
  id: string;
  name: string;
  description: string;
  visibility: Visibility;
  createdAt: string;
  updatedAt: string;
}

export interface KbFile {
  id: string;
  collectionId: string;
  filename: string;
  sizeBytes: number;
  mimeType: string;
  status: FileStatus;
  error: string | null;
  pageCount: number | null;
  contentMd?: string | null;
  indexMd?: string | null;
  createdAt: string;
  updatedAt: string;
}

export const COLLECTIONS_CHANGED = "chatkb:collections-changed";

export function notifyCollectionsChanged(): void {
  window.dispatchEvent(new Event(COLLECTIONS_CHANGED));
}

export function listCollections(): Promise<Collection[]> {
  return api<Collection[]>("/v1/collections");
}

export function getCollection(id: string): Promise<Collection> {
  return api<Collection>(`/v1/collections/${id}`);
}

export function createCollection(body: {
  name: string;
  description?: string;
  visibility?: Visibility;
}): Promise<Collection> {
  return api<Collection>("/v1/collections", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteCollection(id: string): Promise<void> {
  return api<void>(`/v1/collections/${id}`, { method: "DELETE" });
}

export function listFiles(collectionId: string): Promise<KbFile[]> {
  return api<KbFile[]>(`/v1/collections/${collectionId}/files`);
}

export function getFile(
  collectionId: string,
  fileId: string,
): Promise<KbFile> {
  return api<KbFile>(`/v1/collections/${collectionId}/files/${fileId}`);
}

export function uploadFile(
  collectionId: string,
  file: File,
): Promise<KbFile> {
  const body = new FormData();
  body.append("file", file);
  return api<KbFile>(`/v1/collections/${collectionId}/files`, {
    method: "POST",
    body,
  });
}

export function deleteFile(
  collectionId: string,
  fileId: string,
): Promise<void> {
  return api<void>(`/v1/collections/${collectionId}/files/${fileId}`, {
    method: "DELETE",
  });
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) {
    const kb = n / 1024;
    return `${kb >= 10 ? Math.round(kb) : Number(kb.toFixed(1))} KB`;
  }
  const mb = n / (1024 * 1024);
  return `${mb >= 10 ? Math.round(mb) : Number(mb.toFixed(1))} MB`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "Now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return formatDate(iso);
}
