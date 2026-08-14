import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Plus } from "lucide-react";
import { ChatView } from "@/components/ChatView";
import { DetailPanel } from "@/components/DetailPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { avatarClass } from "@/design/tokens";
import { getAgent, getKnowledgeBase, messagesFor } from "@/mocks/data";
import { cn } from "@/lib/utils";

export function AgentDetailPage() {
  const { id } = useParams();
  const agent = id ? getAgent(id) : undefined;
  const [mode, setMode] = useState("builder");

  if (!agent) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        Agent not found.{" "}
        <Link to="/agents" className="text-accent">
          Back to agents
        </Link>
      </div>
    );
  }

  const kbs = agent.knowledgeBaseIds.flatMap((kbId) => {
    const kb = getKnowledgeBase(kbId);
    return kb ? [kb] : [];
  });

  return (
    <DetailPanel
      toolbar={
        <>
          <Button variant="ghost" size="icon" asChild>
            <Link to="/agents" aria-label="Back to agents">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <span className="flex-1 truncate text-sm font-medium">
            {agent.name}
          </span>
          <Button variant="outline">Add to Slack</Button>
          <Button variant="outline">Update</Button>
          <Button>Publish</Button>
        </>
      }
      main={
        <div className="mx-auto flex max-w-composer flex-col gap-8">
          <div className="flex items-start gap-4">
            <div
              className={cn(
                "size-8 shrink-0 rounded-full",
                avatarClass[agent.avatar],
              )}
            />
            <div>
              <h1 className="text-lg font-medium">{agent.name}</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {agent.description}
              </p>
            </div>
          </div>

          <div>
            <PropertyRow label="Connectors">
              <Button variant="outline" size="sm">
                Connect
              </Button>
            </PropertyRow>
            <PropertyRow label="Skills">
              {agent.skills.map((skill) => (
                <Badge key={skill} variant="secondary">
                  {skill}
                </Badge>
              ))}
              <AddPill />
            </PropertyRow>
            <PropertyRow label="Files">
              {kbs.map((kb) => (
                <Link key={kb.id} to={`/kb/${kb.id}`}>
                  <Badge variant="secondary">{kb.name}</Badge>
                </Link>
              ))}
              <AddPill />
            </PropertyRow>
          </div>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-medium">Instructions</h2>
            <p className="text-sm leading-6 text-gray-700">
              {agent.instructions}
            </p>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-medium">How you operate</h2>
            <BulletList items={agent.howYouOperate} />
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-medium">Working effectively</h2>
            <BulletList items={agent.workingEffectively} />
          </section>
        </div>
      }
      aside={
        <ChatView
          messages={messagesFor(agent.builderThreadId)}
          placeholder="Message the builder..."
          showMic={false}
          header={
            <Tabs value={mode} onValueChange={setMode}>
              <TabsList>
                <TabsTrigger value="builder">Builder</TabsTrigger>
                <TabsTrigger value="playground">Playground</TabsTrigger>
              </TabsList>
            </Tabs>
          }
        />
      }
    />
  );
}

function PropertyRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center gap-4 border-b border-border py-4">
      <p className="w-menu shrink-0 text-sm text-muted-foreground">{label}</p>
      <div className="flex flex-1 flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

function AddPill() {
  return (
    <button
      type="button"
      className="inline-flex size-6 items-center justify-center rounded-full border border-border text-gray-500"
      aria-label="Add"
    >
      <Plus className="size-4" />
    </button>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-2 pl-4">
      {items.map((item) => (
        <li key={item} className="list-disc text-sm leading-6 text-gray-700">
          {item}
        </li>
      ))}
    </ul>
  );
}
