import { Link } from "react-router-dom";
import { ActionsMenu } from "@/components/ActionsMenu";
import { Card } from "@/components/ui/card";
import { avatarClass } from "@/design/tokens";
import type { Agent } from "@/mocks/data";
import { cn } from "@/lib/utils";

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <Card className="relative h-full border-transparent bg-gray-fill transition-colors duration-color ease-out hover:bg-gray-200">
      <div className="absolute right-2 top-2">
        <ActionsMenu />
      </div>
      <Link to={`/agents/${agent.id}`} className="block p-4">
        <div
          className={cn(
            "mb-3 size-8 rounded-full saturate-0",
            avatarClass[agent.avatar],
          )}
        />
        <p className="pr-8 text-sm font-medium">{agent.name}</p>
        <p className="mt-1 text-sm text-muted-foreground">{agent.description}</p>
      </Link>
    </Card>
  );
}
