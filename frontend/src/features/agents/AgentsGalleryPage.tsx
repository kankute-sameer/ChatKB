import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { CardGrid } from "@/components/CardGrid";
import { Composer } from "@/components/ChatView";
import { LandingHero } from "@/components/LandingHero";
import { Input } from "@/components/ui/input";
import { AgentCard } from "@/features/agents/AgentCard";
import { useAgentList } from "@/features/agents/useAgentList";
import {
  createAgent,
  deleteAgent,
  notifyAgentsChanged,
  type Agent,
} from "@/lib/agents";
import { createBuildSession } from "@/lib/conversations";
import { cn } from "@/lib/utils";

export function AgentsGalleryPage() {
  const navigate = useNavigate();
  const agents = useAgentList();
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [scope, setScope] = useState<"personal" | "workspace">("personal");

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return agents.filter((agent) => {
      if (scope === "personal" && agent.visibility !== "personal") return false;
      if (scope === "workspace" && agent.visibility !== "workspace") return false;
      if (!needle) return true;
      return (
        agent.name.toLowerCase().includes(needle) ||
        agent.description.toLowerCase().includes(needle)
      );
    });
  }, [query, agents, scope]);

  const onCreate = async (text: string) => {
    if (creating) return;
    setCreating(true);
    try {
      const name = text.trim().slice(0, 80) || "New agent";
      const agent = await createAgent({ name, description: "" });
      notifyAgentsChanged();
      const session = await createBuildSession(agent.id);
      navigate(`/agents/${agent.id}/builder`, {
        state: { pendingText: text, conversationId: session.conversation.id },
      });
    } finally {
      setCreating(false);
    }
  };

  const onDelete = async (agent: Agent) => {
    await deleteAgent(agent.id);
    notifyAgentsChanged();
  };

  return (
    <LandingHero
      title="Build an agent for your work"
      composer={
        <Composer
          initialValue="Create an agent to "
          autoFocus
          disabled={creating}
          onSubmit={(text) => {
            void onCreate(text);
          }}
        />
      }
    >
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-4">
          <div className="relative min-w-0 flex-1">
            <Search
              aria-hidden
              className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-ink-placeholder"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search agents"
              className="h-row rounded-full border-border py-0 pl-12 pr-4 font-sans text-nav font-ui placeholder:text-ink-placeholder"
            />
          </div>
          <div className="flex h-row shrink-0 items-center rounded-full bg-gray-fill p-1">
            <button
              type="button"
              onClick={() => setScope("personal")}
              className={cn(
                "h-full rounded-full px-4 font-sans text-nav font-ui",
                scope === "personal"
                  ? "bg-background text-ink shadow-soft"
                  : "text-ink-muted",
              )}
            >
              My agents
            </button>
            <button
              type="button"
              onClick={() => setScope("workspace")}
              className={cn(
                "h-full rounded-full px-4 font-sans text-nav font-ui",
                scope === "workspace"
                  ? "bg-background text-ink shadow-soft"
                  : "text-ink-muted",
              )}
            >
              Workspace agents
            </button>
          </div>
        </div>
        <CardGrid
          columns={2}
          items={visible}
          getKey={(agent) => agent.id}
          renderItem={(agent) => (
            <AgentCard
              agent={agent}
              onDelete={(item) => {
                void onDelete(item);
              }}
            />
          )}
        />
      </div>
    </LandingHero>
  );
}
