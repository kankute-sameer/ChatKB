import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen } from "lucide-react";
import { ActionsMenu } from "@/components/ActionsMenu";
import { ResourceTable, type ResourceColumn } from "@/components/ResourceTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useCollectionList } from "@/features/kb/useCollectionList";
import {
  createCollection,
  deleteCollection,
  formatDate,
  notifyCollectionsChanged,
  type Collection,
} from "@/lib/kb";

const columns: ResourceColumn<Collection>[] = [
  {
    id: "name",
    header: "Name",
    render: (row) => (
      <div className="flex items-center gap-3">
        <BookOpen className="size-4 text-gray-500" />
        <div>
          <p className="font-medium">{row.name}</p>
          {row.description ? (
            <p className="text-xs text-muted-foreground">{row.description}</p>
          ) : null}
        </div>
      </div>
    ),
  },
  {
    id: "visibility",
    header: "Visibility",
    render: (row) => (
      <Badge variant={row.visibility === "personal" ? "personal" : "secondary"}>
        {row.visibility === "personal" ? "Personal" : "Workspace"}
      </Badge>
    ),
  },
  {
    id: "createdAt",
    header: "Created",
    render: (row) => formatDate(row.createdAt),
  },
  {
    id: "actions",
    header: "",
    className: "w-8",
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
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
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

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || creating) return;
    setCreating(true);
    try {
      const created = await createCollection({ name: trimmed });
      notifyCollectionsChanged();
      setOpen(false);
      setName("");
      navigate(`/kb/${created.id}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="h-full overflow-auto px-8 py-8">
      <div className="mx-auto flex max-w-content flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-medium">Knowledge base</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Files your agents can search.
            </p>
          </div>
          <Button onClick={() => setOpen(true)}>New collection</Button>
        </div>
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search knowledge bases"
        />
        <ResourceTable
          rows={rows}
          columns={columns}
          getRowId={(row) => row.id}
          onRowClick={(row) => navigate(`/kb/${row.id}`)}
          emptyMessage="No collections yet."
        />
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New collection</DialogTitle>
          </DialogHeader>
          <form className="mt-4 flex flex-col gap-4" onSubmit={(e) => void onCreate(e)}>
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Name"
              autoFocus
            />
            <Button type="submit" disabled={creating || !name.trim()}>
              Create
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
