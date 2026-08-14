import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen } from "lucide-react";
import { ActionsMenu } from "@/components/ActionsMenu";
import { ResourceTable, type ResourceColumn } from "@/components/ResourceTable";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { knowledgeBases, type KnowledgeBase } from "@/mocks/data";

const columns: ResourceColumn<KnowledgeBase>[] = [
  {
    id: "name",
    header: "Name",
    render: (row) => (
      <div className="flex items-center gap-3">
        <BookOpen className="size-4 text-gray-500" />
        <div>
          <p className="font-medium">{row.name}</p>
          <p className="text-xs text-muted-foreground">{row.subtitle}</p>
        </div>
      </div>
    ),
  },
  {
    id: "createdBy",
    header: "Created by",
    render: (row) => row.createdBy,
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
    header: "Created at",
    render: (row) => row.createdAt,
  },
  {
    id: "actions",
    header: "",
    className: "w-8",
    render: () => <ActionsMenu />,
  },
];

export function KnowledgeBaseListPage() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return knowledgeBases;
    return knowledgeBases.filter(
      (kb) =>
        kb.name.toLowerCase().includes(needle) ||
        kb.subtitle.toLowerCase().includes(needle),
    );
  }, [query]);

  return (
    <div className="h-full overflow-auto px-8 py-8">
      <div className="mx-auto flex max-w-content flex-col gap-6">
        <div>
          <h1 className="text-lg font-medium">Knowledge base</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Files your agents can search.
          </p>
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
        />
      </div>
    </div>
  );
}
