import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, X } from "lucide-react";
import { ComposerStartDefault } from "@/components/ChatView";
import { DetailPanel } from "@/components/DetailPanel";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Button } from "@/components/ui/button";
import { appearanceClassName } from "@/design/tokens";
import {
  AgentCapabilitiesOverview,
  KnowledgeBasePickerDialog,
  WebSearchConnectorDetail,
} from "@/features/agents/AgentCapabilities";
import { ConversationChat } from "@/features/conversations/ConversationPage";
import {
  getAgent,
  getAgentCollections,
  getAgentInstructions,
  notifyAgentsChanged,
  setAgentCollections,
  updateAgent,
  type Agent,
} from "@/lib/agents";
import {
  createBuildSession,
  type ConversationDetail,
} from "@/lib/conversations";
import { listCollections, type Collection } from "@/lib/kb";
import { cn } from "@/lib/utils";

const composerFooter = (
  <p className="mt-3 text-center text-xs text-muted-foreground">
    AI can make mistakes, please double-check responses.
  </p>
);

type CanvasView = "overview" | "web_search";

export function AgentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [missing, setMissing] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [canvasView, setCanvasView] = useState<CanvasView>("overview");
  const [buildConversation, setBuildConversation] =
    useState<ConversationDetail | null>(null);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [attachedCollections, setAttachedCollections] = useState<Collection[]>([]);
  const [collectionDraft, setCollectionDraft] = useState<string[]>([]);
  const [collectionPickerOpen, setCollectionPickerOpen] = useState(false);
  const [savingCollections, setSavingCollections] = useState(false);
  const [collectionError, setCollectionError] = useState<string | null>(null);

  const refreshAgent = useCallback(async () => {
    if (!id) return;
    try {
      const [latest, instructions] = await Promise.all([
        getAgent(id),
        getAgentInstructions(id),
      ]);
      setAgent({ ...latest, instructions: instructions.instructions });
    } catch {
      setMissing(true);
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    void (async () => {
      try {
        const [session, available, attached] = await Promise.all([
          createBuildSession(id),
          listCollections(),
          getAgentCollections(id),
        ]);
        if (cancelled) return;
        setAgent(session.targetAgent);
        setBuildConversation(session.conversation);
        setCollections(available);
        setAttachedCollections(attached);
      } catch {
        if (!cancelled) setMissing(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const setConnectors = async (connectors: string[]) => {
    if (!agent) return;
    const updated = await updateAgent(agent.id, { connectors });
    setAgent({ ...updated, instructions: agent.instructions });
    notifyAgentsChanged();
  };

  const openCollectionPicker = () => {
    setCollectionDraft(attachedCollections.map((collection) => collection.id));
    setCollectionError(null);
    setCollectionPickerOpen(true);
  };

  const saveCollections = async () => {
    if (!agent) return;
    setSavingCollections(true);
    setCollectionError(null);
    try {
      const attached = await setAgentCollections(agent.id, collectionDraft);
      setAttachedCollections(attached);
      setCollectionPickerOpen(false);
    } catch (error) {
      setCollectionError(
        error instanceof Error ? error.message : "Could not save attachments.",
      );
    } finally {
      setSavingCollections(false);
    }
  };

  if (!id) {
    return null;
  }
  if (missing) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        Agent not found.{" "}
        <Link to="/agents" className="text-accent">
          Back to agents
        </Link>
      </div>
    );
  }
  if (!agent || !buildConversation) {
    return <div className="p-8 text-sm text-muted-foreground">Loading…</div>;
  }

  const hasWebSearch = (agent.connectors ?? []).includes("web_search");

  return (
    <>
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
          <Button
            variant="secondary"
            onClick={() => {
              notifyAgentsChanged();
              navigate(`/agents/${agent.id}`);
            }}
          >
            Save
          </Button>
        </>
      }
      main={
        <div className="mx-auto flex max-w-composer flex-col gap-8">
          {canvasView === "web_search" ? (
            <WebSearchConnectorDetail
              onBack={() => setCanvasView("overview")}
              onRemove={() => {
                void (async () => {
                  await setConnectors(
                    (agent.connectors ?? []).filter(
                      (item) => item !== "web_search",
                    ),
                  );
                  setCanvasView("overview");
                })();
              }}
            />
          ) : (
            <>
              <div className="flex items-start gap-4">
                <div
                  className={cn(
                    "size-8 shrink-0 rounded-full",
                    appearanceClassName(agent.appearance.key),
                  )}
                />
                <div>
                  <h1 className="text-lg font-medium">{agent.name}</h1>
                  <p className="mt-1 font-sans text-nav font-ui text-muted-foreground">
                    {agent.description || "No description yet."}
                  </p>
                </div>
              </div>

              <AgentCapabilitiesOverview
                hasWebSearch={hasWebSearch}
                collections={attachedCollections}
                onOpenWebSearch={() => setCanvasView("web_search")}
                onAddWebSearch={() => {
                  void setConnectors([
                    ...(agent.connectors ?? []),
                    "web_search",
                  ]);
                }}
                onManageCollections={openCollectionPicker}
              />

              <div className="border-t border-border" />

              <section className="flex flex-col gap-3">
                <h2 className="border-b border-dotted border-border pb-2 font-sans text-nav font-medium text-ink">
                  Instructions
                </h2>
                {agent.instructions.trim() ? (
                  <MarkdownBody
                    text={agent.instructions}
                    className="font-sans text-nav font-ui text-ink"
                  />
                ) : (
                  <p className="font-sans text-nav font-ui text-muted-foreground">
                    The builder will write instructions here.
                  </p>
                )}
              </section>
            </>
          )}
        </div>
      }
      aside={
        chatOpen ? (
          <ConversationChat
            conversation={buildConversation}
            showTitle={false}
            placeholder="Ask anything..."
            header={
              <div className="flex items-center justify-end">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Close chat"
                  onClick={() => setChatOpen(false)}
                >
                  <X className="size-4 text-ink-muted" />
                </Button>
              </div>
            }
            composerStart={<ComposerStartDefault />}
            composerFooter={composerFooter}
            onSettled={() => {
              void refreshAgent();
            }}
          />
        ) : undefined
      }
      />
      <KnowledgeBasePickerDialog
        open={collectionPickerOpen}
        collections={collections}
        selectedIds={collectionDraft}
        saving={savingCollections}
        error={collectionError}
        onOpenChange={(open) => {
          if (!savingCollections) setCollectionPickerOpen(open);
        }}
        onToggle={(collectionId) => {
          setCollectionDraft((current) =>
            current.includes(collectionId)
              ? current.filter((id) => id !== collectionId)
              : [...current, collectionId],
          );
        }}
        onSave={() => {
          void saveCollections();
        }}
      />
    </>
  );
}
