import { api } from "@/lib/api";
import type { Agent } from "@/lib/agents";

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
  targetAgentId?: string | null;
  sessionType?: "chat" | "build";
}

export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessage[];
}

export interface BuildSession {
  conversation: ConversationDetail;
  targetAgent: Agent;
  resumed: boolean;
}

export const CONVERSATIONS_CHANGED = "chatkb:conversations-changed";

export function notifyConversationsChanged(): void {
  window.dispatchEvent(new Event(CONVERSATIONS_CHANGED));
}

export function createConversation(
  agentId?: string,
): Promise<ConversationSummary> {
  return api<ConversationSummary>("/v1/conversations", {
    method: "POST",
    body: agentId ? JSON.stringify({ agentId }) : undefined,
  });
}

export function createBuildSession(
  targetAgentId: string,
): Promise<BuildSession> {
  return api<BuildSession>("/v1/build-sessions", {
    method: "POST",
    body: JSON.stringify({ targetAgentId }),
  });
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

export function reasoningFromParts(parts: UIMessagePart[]): string {
  return parts
    .filter((part) => part.type === "reasoning")
    .map((part) => part.text ?? "")
    .join("");
}
