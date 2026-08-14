import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface LandingHeroProps {
  title: ReactNode;
  composer: ReactNode;
  /** Content below the hero (search, grids, etc.) */
  children?: ReactNode;
  contentClassName?: string;
}

/**
 * Shared home / agents landing: same title type, gap, and composer width.
 * With children, stacks from the top so the list sits under the composer.
 * Without children, vertically centers (new chat home).
 */
export function LandingHero({
  title,
  composer,
  children,
  contentClassName,
}: LandingHeroProps) {
  const hasChildren = Boolean(children);

  return (
    <div className="flex h-full flex-col overflow-auto">
      <div
        className={cn(
          "flex flex-col items-center px-8",
          hasChildren
            ? "shrink-0 pt-agent-hero"
            : "min-h-0 flex-1 justify-center",
        )}
      >
        <div className="flex w-full max-w-composer flex-col items-center gap-8">
          {typeof title === "string" ? (
            <h1 className="text-center font-serif text-hero font-hero text-ink">
              {title}
            </h1>
          ) : (
            title
          )}
          <div className="w-full">{composer}</div>
        </div>
      </div>
      {hasChildren ? (
        <div
          className={cn(
            "mx-auto w-full max-w-content px-8 pb-8 pt-6",
            contentClassName,
          )}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
