import type { ReactNode } from "react";
import { tokens } from "@/design/tokens";
import { cn } from "@/lib/utils";

interface CardGridProps<T> {
  items: T[];
  getKey: (item: T) => string;
  renderItem: (item: T) => ReactNode;
  columns?: 2 | 3;
}

export function CardGrid<T>({
  items,
  getKey,
  renderItem,
  columns = 3,
}: CardGridProps<T>) {
  return (
    <div
      className={cn(
        "grid gap-4",
        columns === 2 ? "grid-cols-2" : "grid-cols-3",
      )}
    >
      {items.map((item, index) => (
        <div
          key={getKey(item)}
          className="animate-enter-stagger"
          style={{ animationDelay: `${index * tokens.motion.staggerMs}ms` }}
        >
          {renderItem(item)}
        </div>
      ))}
    </div>
  );
}
