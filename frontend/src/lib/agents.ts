import { api } from "@/lib/api";

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
  return api<Agent[]>("/v2/agents");
}

export function getAgent(id: string): Promise<Agent> {
  return api<Agent>(`/v2/agents/${id}`);
}

export function getAgentInstructions(
  id: string,
): Promise<{ instructions: string }> {
  return api<{ instructions: string }>(`/v2/agents/${id}/instructions`);
}

export function createAgent(body: {
  name: string;
  description?: string;
}): Promise<Agent> {
  return api<Agent>("/v2/agents", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateAgent(
  id: string,
  body: Partial<Pick<Agent, "name" | "description" | "instructions">>,
): Promise<Agent> {
  return api<Agent>(`/v2/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteAgent(id: string): Promise<void> {
  return api<void>(`/v2/agents/${id}`, { method: "DELETE" });
}
