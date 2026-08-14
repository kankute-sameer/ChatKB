import type { ReactNode } from "react";

interface DetailPanelProps {
  toolbar: ReactNode;
  main: ReactNode;
  aside?: ReactNode;
}

export function DetailPanel({ toolbar, main, aside }: DetailPanelProps) {
  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex items-center gap-3 border-b border-border px-4 py-2">
        {toolbar}
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-auto p-8">{main}</div>
        {aside ? (
          <aside className="flex w-1/4 min-w-0 shrink-0 flex-col border-l border-border">
            {aside}
          </aside>
        ) : null}
      </div>
    </div>
  );
}
