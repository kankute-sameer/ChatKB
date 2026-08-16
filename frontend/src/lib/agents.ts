import { api } from "@/lib/api";
import type { Collection } from "@/lib/kb";

export interface AgentAppearance {
  type: "preset";
  key: string;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  instructions: string;
  appearance: AgentAppearance;
  connectors: string[];
  visibility: "personal" | "workspace";
  isBuilder: boolean;
  createdAt: string;
  updatedAt: string;
}

export const AGENTS_CHANGED = "chatkb:agents-changed";

export function notifyAgentsChanged(): void {
  window.dispatchEvent(new Event(AGENTS_CHANGED));
}

export function listAgents(): Promise<Agent[]> {
  return api<Agent[]>("/v1/agents");
}

export function getAgent(id: string): Promise<Agent> {
  return api<Agent>(`/v1/agents/${id}`);
}

export function getAgentInstructions(
  id: string,
): Promise<{ instructions: string }> {
  return api<{ instructions: string }>(`/v1/agents/${id}/instructions`);
}

export function getAgentCollections(id: string): Promise<Collection[]> {
  return api<Collection[]>(`/v1/agents/${id}/collections`);
}

export function setAgentCollections(
  id: string,
  collectionIds: string[],
): Promise<Collection[]> {
  return api<Collection[]>(`/v1/agents/${id}/collections`, {
    method: "PUT",
    body: JSON.stringify({ collectionIds }),
  });
}

export function createAgent(body: {
  name: string;
  description?: string;
}): Promise<Agent> {
  return api<Agent>("/v1/agents", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateAgent(
  id: string,
  body: Partial<
    Pick<Agent, "name" | "description" | "instructions" | "connectors">
  >,
): Promise<Agent> {
  return api<Agent>(`/v1/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteAgent(id: string): Promise<void> {
  return api<void>(`/v1/agents/${id}`, { method: "DELETE" });
}
