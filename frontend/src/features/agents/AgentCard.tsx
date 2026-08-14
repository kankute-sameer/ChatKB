import { Link, useNavigate } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";
import { ActionsMenu } from "@/components/ActionsMenu";
import { Card } from "@/components/ui/card";
import { appearanceClassName } from "@/design/tokens";
import type { Agent } from "@/lib/agents";
import { cn } from "@/lib/utils";

export function AgentCard({
  agent,
  onDelete,
}: {
  agent: Agent;
  onDelete?: (agent: Agent) => void;
}) {
  const navigate = useNavigate();

  return (
    <Card className="relative h-full border-transparent bg-gray-fill transition-transform duration-color ease-out hover:scale-[0.98]">
      <div className="absolute right-3 top-3">
        <ActionsMenu
          items={[
            { label: "Edit", icon: <Pencil className="size-4" /> },
            ...(onDelete
              ? [{ label: "Delete", icon: <Trash2 className="size-4" /> }]
              : []),
          ]}
          onSelect={(item) => {
            if (item === "Edit") {
              navigate(`/agents/${agent.id}/builder`);
            }
            if (item === "Delete") onDelete?.(agent);
          }}
        />
      </div>
      <Link to={`/agents/${agent.id}`} className="block p-6">
        <div
          className={cn(
            "mb-4 size-12 rounded-full",
            appearanceClassName(agent.appearance?.key),
          )}
        />
        <p className="pr-8 font-sans text-nav font-medium text-ink">{agent.name}</p>
        <p className="mt-2 line-clamp-2 font-sans text-nav font-ui text-muted-foreground">
          {agent.description}
        </p>
      </Link>
    </Card>
  );
}
