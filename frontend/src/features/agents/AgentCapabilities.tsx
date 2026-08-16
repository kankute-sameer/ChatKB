import { useMemo, useState, type ReactNode } from "react";
import { FileText, Globe, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { Collection } from "@/lib/kb";
import { cn } from "@/lib/utils";

function Chip({
  icon,
  label,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  onClick?: () => void;
}) {
  const className = cn(
    "inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1.5 font-sans text-nav font-ui text-ink",
    onClick && "cursor-pointer hover:bg-gray-50",
  );
  if (onClick) {
    return (
      <button type="button" className={className} onClick={onClick}>
        {icon}
        {label}
      </button>
    );
  }
  return (
    <span className={className}>
      {icon}
      {label}
    </span>
  );
}

function AddCircle({
  label,
  onClick,
}: {
  label: string;
  onClick?: () => void;
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className="size-8 shrink-0 rounded-full"
      aria-label={label}
      onClick={onClick}
      disabled={!onClick}
    >
      <Plus className="size-4" />
    </Button>
  );
}

export function AgentCapabilitiesOverview({
  hasWebSearch,
  collections,
  onOpenWebSearch,
  onAddWebSearch,
  onManageCollections,
}: {
  hasWebSearch: boolean;
  collections: Collection[];
  onOpenWebSearch: () => void;
  onAddWebSearch: () => void;
  onManageCollections: () => void;
}) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <span className="w-24 shrink-0 font-sans text-nav font-medium text-ink">
          Connectors
        </span>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {hasWebSearch ? (
            <Chip
              icon={<Globe className="size-4 shrink-0 text-ink" />}
              label="Web Search"
              onClick={onOpenWebSearch}
            />
          ) : null}
          {!hasWebSearch ? (
            <AddCircle label="Add connector" onClick={onAddWebSearch} />
          ) : (
            <AddCircle label="Add connector" />
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span className="w-24 shrink-0 font-sans text-nav font-medium text-ink">
          Files
        </span>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {collections.map((collection) => (
            <Chip
              key={collection.id}
              icon={<FileText className="size-4 shrink-0 text-ink" />}
              label={collection.name}
              onClick={onManageCollections}
            />
          ))}
          <AddCircle label="Manage knowledge bases" onClick={onManageCollections} />
        </div>
      </div>
    </div>
  );
}

export function KnowledgeBasePickerDialog({
  open,
  collections,
  attachedIds,
  connectingId,
  error,
  onOpenChange,
  onConnect,
  onRemove,
}: {
  open: boolean;
  collections: Collection[];
  attachedIds: string[];
  connectingId: string | null;
  error: string | null;
  onOpenChange: (open: boolean) => void;
  onConnect: (collectionId: string) => void;
  onRemove: (collectionId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const attached = new Set(attachedIds);
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return collections.filter((collection) => {
      if (!needle) return true;
      return (
        collection.name.toLowerCase().includes(needle) ||
        collection.description.toLowerCase().includes(needle)
      );
    });
  }, [collections, query]);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setQuery("");
        onOpenChange(next);
      }}
    >
      <DialogContent className="w-[min(780px,calc(100vw-4rem))] max-w-none rounded-lg px-8 py-10">
        <DialogHeader>
          <DialogTitle className="text-title font-normal">
            Add knowledge base
          </DialogTitle>
          <p className="mt-2 font-sans text-nav font-ui text-ink-muted">
            Choose which knowledge bases your agent can retrieve from.
          </p>
        </DialogHeader>

        <div className="relative mt-8">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-ink-placeholder"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search"
            className="rounded-full pl-12 focus-visible:ring-gray-300"
          />
        </div>

        <div className="mt-4 min-h-72 max-h-[28rem] overflow-y-auto rounded-xl border border-border">
          {visible.length ? (
            visible.map((collection) => {
              const isAttached = attached.has(collection.id);
              const busy = connectingId === collection.id;
              return (
                <div
                  key={collection.id}
                  className="flex items-center gap-3 border-b border-border px-4 py-3 last:border-b-0"
                >
                  <FileText className="size-5 shrink-0 text-ink-muted" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-sans text-nav font-ui font-medium text-ink">
                      {collection.name}
                    </p>
                    <p className="truncate font-sans text-nav font-ui text-ink-muted">
                      {collection.description || collection.name}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="pill"
                    className="shrink-0"
                    disabled={busy}
                    onClick={() =>
                      isAttached
                        ? onRemove(collection.id)
                        : onConnect(collection.id)
                    }
                  >
                    {busy
                      ? isAttached
                        ? "Removing…"
                        : "Connecting…"
                      : isAttached
                        ? "Remove"
                        : "Connect"}
                  </Button>
                </div>
              );
            })
          ) : (
            <p className="px-4 py-8 text-center font-sans text-nav font-ui text-ink-muted">
              {collections.length === 0
                ? "No knowledge bases yet. Create one from Knowledge Bases first."
                : "No knowledge bases match your search."}
            </p>
          )}
        </div>

        {error ? (
          <p className="mt-3 font-sans text-nav font-ui text-destructive">{error}</p>
        ) : null}
        <div className="mt-5 flex justify-end">
          <Button
            type="button"
            className="rounded-full bg-gray-900 px-6 text-white hover:bg-gray-800"
            onClick={() => onOpenChange(false)}
            disabled={connectingId != null}
          >
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function WebSearchConnectorDetail({
  onBack,
  onRemove,
}: {
  onBack: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <button
        type="button"
        onClick={onBack}
        className="flex w-fit items-center gap-2 font-sans text-nav font-ui text-ink-muted hover:text-ink"
      >
        <span aria-hidden>←</span>
        Back
      </button>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <Globe className="mt-0.5 size-5 shrink-0 text-ink" />
          <div>
            <p className="font-sans text-nav font-medium text-ink">Web Search</p>
            <p className="mt-0.5 font-sans text-nav font-ui text-ink-muted">
              Connected
            </p>
          </div>
        </div>
        <Button type="button" variant="secondary" size="pill" onClick={onRemove}>
          Remove from agent
        </Button>
      </div>
    </div>
  );
}
