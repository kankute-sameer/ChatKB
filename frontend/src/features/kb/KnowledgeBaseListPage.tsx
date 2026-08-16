import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, Search } from "lucide-react";
import { ActionsMenu } from "@/components/ActionsMenu";
import { ResourceTable, type ResourceColumn } from "@/components/ResourceTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CreateKnowledgeBaseDialog } from "@/features/kb/CreateKnowledgeBaseDialog";
import { useCollectionList } from "@/features/kb/useCollectionList";
import {
  deleteCollection,
  formatDate,
  notifyCollectionsChanged,
  type Collection,
} from "@/lib/kb";

const columns: ResourceColumn<Collection>[] = [
  {
    id: "name",
    header: "Name",
    className: "w-[50%]",
    render: (row) => (
      <div className="flex items-center gap-3">
        <BookOpen className="size-5 text-gray-500" />
        <div className="min-w-0">
          <p className="truncate font-sans text-nav font-ui font-normal">{row.name}</p>
          {row.description ? (
          <p className="truncate text-nav text-muted-foreground">{row.description}</p>
          ) : null}
        </div>
      </div>
    ),
  },
  {
    id: "visibility",
    header: "Visibility",
    className: "w-[20%]",
    render: (row) => (
      <Badge variant={row.visibility === "personal" ? "personal" : "secondary"}>
        {row.visibility === "personal" ? "Personal" : "Workspace"}
      </Badge>
    ),
  },
  {
    id: "createdAt",
    header: "Created",
    className: "w-[20%]",
    render: (row) => (
      <span className="text-ink-placeholder">{formatDate(row.createdAt)}</span>
    ),
  },
  {
    id: "actions",
    header: "",
    className: "w-14 text-right",
    render: (row) => (
      <ActionsMenu
        items={["Delete"]}
        onSelect={(item) => {
          if (item === "Delete") {
            void deleteCollection(row.id).then(notifyCollectionsChanged);
          }
        }}
      />
    ),
  },
];

export function KnowledgeBaseListPage() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const collections = useCollectionList();

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return collections;
    return collections.filter(
      (kb) =>
        kb.name.toLowerCase().includes(needle) ||
        kb.description.toLowerCase().includes(needle),
    );
  }, [query, collections]);

  return (
    <div className="h-full overflow-auto px-8 py-8">
      <div className="flex w-full flex-col gap-6">
        <div className="flex items-center justify-between gap-4">
          <h1 className="font-sans text-nav font-ui font-normal">Knowledge base</h1>
          <Button
            className="shrink-0 rounded-full bg-gray-900 text-white hover:bg-gray-800"
            onClick={() => setOpen(true)}
          >
            + New knowledge base
          </Button>
        </div>
        <div className="mx-auto flex w-2/3 flex-col gap-6">
          <div className="relative w-1/3">
            <Search
              aria-hidden
              className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-ink-placeholder"
            />
            <Input
              className="rounded-full pl-12 focus-visible:ring-gray-300"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search knowledge bases"
            />
          </div>
          <ResourceTable
            className="rounded-lg"
            rows={rows}
            columns={columns}
            getRowId={(row) => row.id}
            onRowClick={(row) => navigate(`/kb/${row.id}`)}
            emptyMessage="No collections yet."
          />
        </div>
      </div>
      <CreateKnowledgeBaseDialog
        open={open}
        onOpenChange={setOpen}
        onCreated={(id) => navigate(`/kb/${id}`)}
      />
    </div>
  );
}
