import { useMemo, useState } from "react";
import { CardGrid } from "@/components/CardGrid";
import { Composer } from "@/components/ChatView";
import { LandingHero } from "@/components/LandingHero";
import { Input } from "@/components/ui/input";
import { AgentCard } from "@/features/agents/AgentCard";
import { agents } from "@/mocks/data";

export function AgentsGalleryPage() {
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return agents;
    return agents.filter(
      (agent) =>
        agent.name.toLowerCase().includes(needle) ||
        agent.description.toLowerCase().includes(needle),
    );
  }, [query]);

  return (
    <LandingHero
      title="Build an agent for your work"
      composer={<Composer placeholder="Create an agent to" showMic={false} />}
    >
      <div className="flex flex-col gap-6">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search agents"
          className="max-w-composer"
        />
        <CardGrid
          items={visible}
          getKey={(agent) => agent.id}
          renderItem={(agent) => <AgentCard agent={agent} />}
        />
      </div>
    </LandingHero>
  );
}
