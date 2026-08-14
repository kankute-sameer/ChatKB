import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Composer, ComposerStartDefault } from "@/components/ChatView";
import { LandingHero } from "@/components/LandingHero";
import { appearanceClassName } from "@/design/tokens";
import { getAgent, type Agent } from "@/lib/agents";
import {
  createConversation,
  notifyConversationsChanged,
} from "@/lib/conversations";
import { cn } from "@/lib/utils";

export function AgentChatPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    getAgent(id)
      .then((latest) => {
        if (!cancelled) setAgent(latest);
      })
      .catch(() => {
        if (!cancelled) setMissing(true);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!id) return null;
  if (missing) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        Agent not found.{" "}
        <Link to="/agents" className="text-accent">
          Back to agents
        </Link>
      </div>
    );
  }
  if (!agent) {
    return <div className="p-8 text-sm text-muted-foreground">Loading…</div>;
  }

  const onSubmit = async (text: string) => {
    const conversation = await createConversation(agent.id);
    notifyConversationsChanged();
    navigate(`/c/${conversation.id}`, { state: { pendingText: text } });
  };

  return (
    <LandingHero
      title={
        <div className="flex flex-col items-center gap-6">
          <div
            className={cn(
              "size-8 rounded-full",
              appearanceClassName(agent.appearance.key),
            )}
          />
          <h1 className="text-center font-serif text-hero font-hero text-ink">
            {agent.name}
          </h1>
        </div>
      }
      composer={
        <Composer
          placeholder="Ask anything..."
          start={<ComposerStartDefault />}
          onSubmit={(text) => {
            void onSubmit(text);
          }}
        />
      }
    />
  );
}
