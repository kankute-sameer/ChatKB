import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FileText } from "lucide-react";
import { ActionsMenu } from "@/components/ActionsMenu";
import { CardGrid } from "@/components/CardGrid";
import { ResourceTable, type ResourceColumn } from "@/components/ResourceTable";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AgentCard } from "@/features/agents/AgentCard";
import type { Agent as LiveAgent } from "@/lib/agents";
import {
  agentsForKb,
  filesFor,
  getKnowledgeBase,
  type Agent as MockAgent,
  type KBFile,
} from "@/mocks/data";

const fileColumns: ResourceColumn<KBFile>[] = [
  {
    id: "name",
    header: "Name",
    render: (row) => (
      <div className="flex items-center gap-3">
        <FileText className="size-4 text-gray-500" />
        <span className="font-medium">{row.name}</span>
      </div>
    ),
  },
  {
    id: "size",
    header: "Size",
    render: (row) => row.size,
  },
  {
    id: "status",
    header: "Status",
    render: (row) => (
      <Badge variant={row.status === "ready" ? "success" : "secondary"}>
        {row.status === "ready" ? "Ready" : "Processing"}
      </Badge>
    ),
  },
  {
    id: "addedAt",
    header: "Added",
    render: (row) => row.addedAt,
  },
  {
    id: "actions",
    header: "",
    className: "w-8",
    render: () => <ActionsMenu items={["Download", "Remove"]} />,
  },
];

export function KnowledgeBaseDetailPage() {
  const { id } = useParams();
  const kb = id ? getKnowledgeBase(id) : undefined;
  const [query, setQuery] = useState("");

  const files = useMemo(() => {
    if (!kb) return [];
    const needle = query.trim().toLowerCase();
    const rows = filesFor(kb.id);
    if (!needle) return rows;
    return rows.filter((file) => file.name.toLowerCase().includes(needle));
  }, [kb, query]);

  if (!kb) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        Knowledge base not found.{" "}
        <Link to="/kb" className="text-accent">
          Back
        </Link>
      </div>
    );
  }

  const linkedAgents = agentsForKb(kb);

  return (
    <div className="h-full overflow-auto px-8 py-8">
      <div className="mx-auto flex max-w-content flex-col gap-6">
        <div>
          <Link to="/kb" className="text-xs text-muted-foreground">
            Knowledge base
          </Link>
          <h1 className="mt-2 text-lg font-medium">{kb.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{kb.subtitle}</p>
        </div>

        <Tabs defaultValue="files">
          <TabsList>
            <TabsTrigger value="files">Files ({files.length})</TabsTrigger>
            <TabsTrigger value="agents">
              Agents ({linkedAgents.length})
            </TabsTrigger>
          </TabsList>
          <TabsContent value="files">
            <div className="flex flex-col gap-4">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search files"
              />
              <ResourceTable
                rows={files}
                columns={fileColumns}
                getRowId={(row) => row.id}
              />
            </div>
          </TabsContent>
          <TabsContent value="agents">
            <CardGrid
              items={linkedAgents}
              getKey={(agent) => agent.id}
              renderItem={(agent) => (
                <AgentCard agent={toLiveAgent(agent)} />
              )}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function toLiveAgent(agent: MockAgent): LiveAgent {
  return {
    id: agent.id,
    name: agent.name,
    description: agent.description,
    instructions: agent.instructions,
    appearance: {
      type: "preset",
      key: agent.avatar === "red" ? "red-blur" : "blue-blur",
    },
    visibility: agent.scope === "workspace" ? "workspace" : "personal",
    isBuilder: agent.id === "agent-creator",
    createdAt: "",
    updatedAt: "",
  };
}
