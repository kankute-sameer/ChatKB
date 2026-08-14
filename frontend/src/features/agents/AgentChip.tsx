import { appearanceClassName } from "@/design/tokens";
import type { Agent } from "@/lib/agents";
import { cn } from "@/lib/utils";

export function AgentChip({ agent }: { agent: Agent }) {
  return (
    <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-border bg-gray-fill px-3 py-1">
      <span
        className={cn(
          "size-3 shrink-0 rounded-full",
          appearanceClassName(agent.appearance.key),
        )}
      />
      <span className="truncate font-sans text-nav font-ui text-ink">
        {agent.name}
      </span>
    </div>
  );
}
