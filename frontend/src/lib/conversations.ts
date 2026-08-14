import { api } from "@/lib/api";

export interface UIMessagePart {
  type: string;
  text?: string;
  state?: string;
  [key: string]: unknown;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  parts: UIMessagePart[];
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  activeResponseId: string | null;
  lastEventId: number | null;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessage[];
}

export const CONVERSATIONS_CHANGED = "chatkb:conversations-changed";

export function notifyConversationsChanged(): void {
  window.dispatchEvent(new Event(CONVERSATIONS_CHANGED));
}

export function createConversation(): Promise<ConversationSummary> {
  return api<ConversationSummary>("/v1/conversations", { method: "POST" });
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return api<ConversationDetail>(`/v1/conversations/${id}`);
}

export function listConversations(): Promise<ConversationSummary[]> {
  return api<ConversationSummary[]>("/v1/conversations?limit=50");
}

export function stoppedStorageKey(conversationId: string): string {
  return `chatkb.stopped:${conversationId}`;
}

export function textFromParts(parts: UIMessagePart[]): string {
  return parts
    .filter((part) => part.type === "text")
    .map((part) => part.text ?? "")
    .join("");
}
