import type { ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export type ActionMenuItem = string | { label: string; icon?: ReactNode };

interface ActionsMenuProps {
  items?: ActionMenuItem[];
  onSelect?: (item: string) => void;
}

function labelOf(item: ActionMenuItem): string {
  return typeof item === "string" ? item : item.label;
}

export function ActionsMenu({
  items = ["Rename", "Copy link", "Delete"],
  onSelect,
}: ActionsMenuProps) {
  if (items.length === 0) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open actions"
          onClick={(event) => event.stopPropagation()}
        >
          <MoreHorizontal className="size-4 text-gray-500" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {items.map((item) => {
          const label = labelOf(item);
          const icon = typeof item === "string" ? null : item.icon;
          return (
            <DropdownMenuItem
              key={label}
              onClick={(event) => {
                event.stopPropagation();
                onSelect?.(label);
              }}
            >
              {icon ? (
                <span className="mr-2 inline-flex size-4 shrink-0 items-center justify-center text-gray-500">
                  {icon}
                </span>
              ) : null}
              {label}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
