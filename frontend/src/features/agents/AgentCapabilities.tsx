import type { ReactNode } from "react";
import { FileText, Globe, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  selectedIds,
  saving,
  error,
  onOpenChange,
  onToggle,
  onSave,
}: {
  open: boolean;
  collections: Collection[];
  selectedIds: string[];
  saving: boolean;
  error: string | null;
  onOpenChange: (open: boolean) => void;
  onToggle: (collectionId: string) => void;
  onSave: () => void;
}) {
  const selected = new Set(selectedIds);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Attach knowledge bases</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Choose which collections this agent can search.
          </p>
        </DialogHeader>

        <div className="my-5 max-h-72 overflow-y-auto rounded border border-border">
          {collections.length ? (
            collections.map((collection) => (
              <label
                key={collection.id}
                className="flex cursor-pointer items-start gap-3 border-b border-border px-4 py-3 last:border-b-0 hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={selected.has(collection.id)}
                  onChange={() => onToggle(collection.id)}
                  className="mt-1 size-4 accent-foreground"
                />
                <FileText className="mt-0.5 size-4 shrink-0 text-ink-muted" />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-ink">
                    {collection.name}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {collection.description || "No description"}
                  </span>
                </span>
              </label>
            ))
          ) : (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              No knowledge bases yet. Create one from Knowledge Bases first.
            </p>
          )}
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button type="button" onClick={onSave} disabled={saving}>
            {saving ? "Saving…" : "Save attachments"}
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
            <p className="mt-0.5 font-sans text-sm font-ui text-muted-foreground">
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
