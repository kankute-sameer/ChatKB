import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Check,
  ChevronDown,
  CloudUpload,
  FileWarning,
  Loader2,
  Plus,
  Search,
  X,
} from "lucide-react";
import { ActionsMenu } from "@/components/ActionsMenu";
import { FileTypeIcon } from "@/components/FileTypeIcon";
import { ResourceViewer } from "@/components/ResourceViewer";
import { ResourceTable, type ResourceColumn } from "@/components/ResourceTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { appearanceClassName } from "@/design/tokens";
import { useCollectionList } from "@/features/kb/useCollectionList";
import { listAgents, type Agent } from "@/lib/agents";
import { cn } from "@/lib/utils";
import {
  attachCollectionAgent,
  deleteFile,
  detachCollectionAgent,
  formatBytes,
  formatRelativeDate,
  getCollection,
  listCollectionAgents,
  listFiles,
  uploadFile,
  type Collection,
  type FileStatus,
  type KbFile,
} from "@/lib/kb";

const SUPPORTED_FILE_PATTERN = /\.(pdf|docx|txt|md|csv|tsv|json)$/i;
const ACCEPTED_FILE_TYPES = ".pdf,.docx,.txt,.md,.csv,.tsv,.json";
const SCANNED_PDF_ERROR = "Scanned PDFs are not supported";

type DetailTab = "files" | "agents";

function StatusBadge({ status, error }: { status: FileStatus; error: string | null }) {
  if (status === "processing") {
    return (
      <Badge variant="warning" className="gap-1 px-3 font-sans text-nav font-ui font-normal">
        <Loader2 className="size-4 animate-spin" />
        Processing
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge
        variant="danger"
        title={error ?? undefined}
        className="px-3 font-sans text-nav font-ui font-normal"
      >
        Failed
      </Badge>
    );
  }
  return (
    <Badge variant="success" className="px-3 font-sans text-nav font-ui font-normal">
      Ready
    </Badge>
  );
}

export function KnowledgeBaseDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const collections = useCollectionList();
  const inputRef = useRef<HTMLInputElement>(null);
  const shownIngestionErrors = useRef(new Set<string>());
  const [collection, setCollection] = useState<Collection | null>(null);
  const [missing, setMissing] = useState(false);
  const [files, setFiles] = useState<KbFile[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [allAgents, setAllAgents] = useState<Agent[]>([]);
  const [tab, setTab] = useState<DetailTab>("files");
  const [query, setQuery] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ingestionFailure, setIngestionFailure] = useState<KbFile | null>(null);
  const [openFile, setOpenFile] = useState<KbFile | null>(null);
  const [addAgentOpen, setAddAgentOpen] = useState(false);
  const [agentQuery, setAgentQuery] = useState("");
  const [attachingId, setAttachingId] = useState<string | null>(null);

  useEffect(() => {
    setOpenFile(null);
    setTab("files");
    setQuery("");
    setError(null);
    setIngestionFailure(null);
    shownIngestionErrors.current.clear();
  }, [id]);

  const loadFiles = useCallback(async (collectionId: string) => {
    const rows = await listFiles(collectionId);
    setFiles(rows);
  }, []);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    void (async () => {
      try {
        const [latest, rows, connected] = await Promise.all([
          getCollection(id),
          listFiles(id),
          listCollectionAgents(id),
        ]);
        if (cancelled) return;
        setCollection(latest);
        setFiles(rows);
        setAgents(connected);
      } catch {
        if (!cancelled) setMissing(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const processing = files.some((file) => file.status === "processing");

  useEffect(() => {
    if (!id || !processing) return;
    const timer = window.setInterval(() => {
      void loadFiles(id);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [id, processing, loadFiles]);

  useEffect(() => {
    if (ingestionFailure) return;
    const failed = files.find(
      (file) =>
        file.status === "failed" &&
        file.error?.includes(SCANNED_PDF_ERROR) &&
        !shownIngestionErrors.current.has(file.id),
    );
    if (!failed) return;
    shownIngestionErrors.current.add(failed.id);
    setIngestionFailure(failed);
  }, [files, ingestionFailure]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return files;
    return files.filter((file) => file.filename.toLowerCase().includes(needle));
  }, [files, query]);

  const availableAgents = useMemo(() => {
    const needle = agentQuery.trim().toLowerCase();
    return allAgents.filter((agent) => {
      if (!needle) return true;
      return (
        agent.name.toLowerCase().includes(needle) ||
        agent.description.toLowerCase().includes(needle)
      );
    });
  }, [agentQuery, allAgents]);

  const connectedAgentIds = useMemo(
    () => new Set(agents.map((agent) => agent.id)),
    [agents],
  );

  const onUpload = async (list: FileList | File[]) => {
    if (!id || uploading) return;
    const accepted = Array.from(list).filter((file) =>
      SUPPORTED_FILE_PATTERN.test(file.name),
    );
    if (accepted.length === 0) {
      setError("Choose a PDF, DOCX, TXT, MD, CSV, TSV, or JSON file");
      return;
    }
    setError(null);
    setUploading(true);
    try {
      for (const file of accepted) {
        const created = await uploadFile(id, file);
        setFiles((current) => [
          created,
          ...current.filter((row) => row.id !== created.id),
        ]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onDelete = async (file: KbFile) => {
    if (!id) return;
    await deleteFile(id, file.id);
    setFiles((current) => current.filter((row) => row.id !== file.id));
  };

  const openAddAgent = async () => {
    if (!id) return;
    setError(null);
    setAgentQuery("");
    try {
      const rows = await listAgents();
      setAllAgents(rows);
      setAddAgentOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load agents");
    }
  };

  const onAttach = async (agent: Agent) => {
    if (!id || attachingId) return;
    setAttachingId(agent.id);
    setError(null);
    try {
      const attached = await attachCollectionAgent(id, agent.id);
      setAgents((current) =>
        current.some((row) => row.id === attached.id)
          ? current
          : [...current, attached],
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not connect agent");
    } finally {
      setAttachingId(null);
    }
  };

  const onDetach = async (agent: Agent) => {
    if (!id || attachingId) return;
    setAttachingId(agent.id);
    setError(null);
    try {
      await detachCollectionAgent(id, agent.id);
      setAgents((current) => current.filter((row) => row.id !== agent.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove agent");
    } finally {
      setAttachingId(null);
    }
  };

  const fileColumns: ResourceColumn<KbFile>[] = [
    {
      id: "name",
      header: "Name",
      className: "w-[42%]",
      render: (row) => (
        <div className="flex min-w-0 items-center gap-3">
          <FileTypeIcon filename={row.filename} className="size-8" />
          <div className="min-w-0">
            <div className="truncate font-normal text-foreground">{row.filename}</div>
            {row.status === "processing" ? (
              <div className="truncate font-sans text-nav font-ui text-ink-muted">
                {row.ingestionStage} · {row.ingestionProgress}%
              </div>
            ) : null}
          </div>
        </div>
      ),
    },
    {
      id: "size",
      header: "Size",
      className: "w-[14%]",
      render: (row) => (
        <span className="text-ink-muted">{formatBytes(row.sizeBytes)}</span>
      ),
    },
    {
      id: "status",
      header: "Status",
      className: "w-[16%]",
      render: (row) => <StatusBadge status={row.status} error={row.error} />,
    },
    {
      id: "addedAt",
      header: "Added",
      className: "w-[18%]",
      render: (row) => (
        <span className="text-ink-placeholder">{formatRelativeDate(row.createdAt)}</span>
      ),
    },
    {
      id: "actions",
      header: "",
      className: "w-14 text-right",
      render: (row) => (
        <ActionsMenu
          items={["Remove"]}
          onSelect={(item) => {
            if (item === "Remove") void onDelete(row);
          }}
        />
      ),
    },
  ];

  if (missing || !id) {
    return (
      <div className="p-8 font-sans text-nav font-ui text-muted-foreground">
        Knowledge base not found.{" "}
        <Link to="/kb" className="text-foreground underline">
          Back
        </Link>
      </div>
    );
  }

  if (!collection) {
    return (
      <div className="p-8 font-sans text-nav font-ui text-muted-foreground">
        Loading…
      </div>
    );
  }

  return (
    <>
      <div
        className="h-full overflow-auto px-8 py-8 font-sans text-nav font-ui transition-[margin] duration-200"
        style={{
          marginRight: openFile ? "clamp(36rem, 60vw, 64rem)" : undefined,
        }}
      >
        <div className="flex w-full flex-col gap-6">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Link to="/kb" className="text-muted-foreground hover:text-foreground">
              Knowledge base
            </Link>
            <span className="text-muted-foreground" aria-hidden>
              /
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="inline-flex max-w-full items-center gap-1 rounded px-1 font-normal text-foreground hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-300"
                >
                  <span className="truncate">{collection.name}</span>
                  <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="min-w-56 rounded-lg">
                {collections.map((item) => {
                  const selected = item.id === collection.id;
                  return (
                    <DropdownMenuItem
                      key={item.id}
                      className="gap-2 py-2"
                      onSelect={() => {
                        if (!selected) navigate(`/kb/${item.id}`);
                      }}
                    >
                      <Check
                        className={cn(
                          "size-4 shrink-0",
                          selected ? "text-foreground" : "opacity-0",
                        )}
                      />
                      <span className="min-w-0 truncate">{item.name}</span>
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className="mx-auto flex w-5/6 flex-col gap-6">
            <div className="flex items-center gap-6 border-b border-border">
              {(
                [
                  { id: "files", label: "Files", count: files.length },
                  { id: "agents", label: "Agents", count: agents.length },
                ] as const
              ).map((item) => {
                const active = tab === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setTab(item.id)}
                    className={cn(
                      "inline-flex items-center gap-2 border-b-2 pb-3 font-sans text-nav font-ui",
                      active
                        ? "border-foreground text-foreground"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {item.label}
                    <span className="inline-flex min-w-6 items-center justify-center rounded-full bg-gray-100 px-2 py-0.5 text-ink-muted">
                      {item.count}
                    </span>
                  </button>
                );
              })}
            </div>

            {error ? <p className="text-destructive">{error}</p> : null}

            {tab === "files" ? (
              <>
                <div
                  className={cn(
                    "flex items-center gap-4 rounded-lg border border-dashed border-border px-4 py-8",
                    dragOver && "border-gray-400 bg-gray-50",
                  )}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDragOver(false);
                    void onUpload(event.dataTransfer.files);
                  }}
                >
                  <CloudUpload className="size-5 shrink-0 text-gray-400" />
                  <p className="min-w-0 flex-1 text-muted-foreground">
                    Drag and drop PDF, DOCX, TXT, MD, CSV, TSV, or JSON files
                  </p>
                  <Button
                    type="button"
                    className="shrink-0 rounded-full bg-gray-900 text-white hover:bg-gray-800"
                    disabled={uploading}
                    onClick={() => inputRef.current?.click()}
                  >
                    {uploading ? "Uploading…" : "Browse files"}
                  </Button>
                  <input
                    ref={inputRef}
                    type="file"
                    accept={ACCEPTED_FILE_TYPES}
                    multiple
                    className="hidden"
                    onChange={(event) => {
                      if (event.target.files) void onUpload(event.target.files);
                      event.target.value = "";
                    }}
                  />
                </div>

                <div className="relative w-1/3">
                  <Search
                    aria-hidden
                    className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-ink-placeholder"
                  />
                  <Input
                    className="rounded-full pl-12 focus-visible:ring-gray-300"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search files"
                  />
                </div>

                <ResourceTable
                  className="rounded-lg"
                  rows={visible}
                  columns={fileColumns}
                  getRowId={(row) => row.id}
                  onRowClick={(row) => {
                    if (row.status === "ready") {
                      setOpenFile(row);
                    }
                  }}
                  emptyMessage="No files yet. Upload a PDF to ingest it."
                />
              </>
            ) : (
              <div className="flex flex-col gap-6">
                <div>
                  <h2 className="font-sans text-nav font-ui font-medium text-ink">
                    Connected agents
                  </h2>
                  <p className="mt-1 font-sans text-nav font-ui text-ink-muted">
                    Agents that can retrieve from this knowledge base.
                  </p>
                </div>

                <div className="divide-y divide-border border-y border-border">
                  {agents.length === 0 ? (
                    <p className="py-8 font-sans text-nav font-ui text-ink-muted">
                      No agents connected yet.
                    </p>
                  ) : (
                    agents.map((agent) => (
                      <div
                        key={agent.id}
                        className="flex items-start gap-4 py-4"
                      >
                        <span
                          className={cn(
                            "mt-1 size-10 shrink-0 rounded-full",
                            appearanceClassName(agent.appearance?.key),
                          )}
                          aria-hidden
                        />
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-sans text-nav font-ui font-medium text-ink">
                            {agent.name}
                          </p>
                          <p className="mt-1 line-clamp-2 font-sans text-nav font-ui text-ink-muted">
                            {agent.description || "No description"}
                          </p>
                        </div>
                        <button
                          type="button"
                          aria-label={`Remove ${agent.name}`}
                          className="rounded-full p-2 text-ink-muted hover:bg-gray-100 hover:text-ink"
                          onClick={() => void onDetach(agent)}
                        >
                          <X className="size-4" />
                        </button>
                      </div>
                    ))
                  )}
                </div>

                <div>
                  <Button
                    type="button"
                    variant="secondary"
                    className="rounded-lg"
                    onClick={() => void openAddAgent()}
                  >
                    <Plus className="size-4" />
                    Add agent
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <Dialog
        open={ingestionFailure != null}
        onOpenChange={(open) => {
          if (!open) setIngestionFailure(null);
        }}
      >
        <DialogContent
          aria-describedby={undefined}
          className="w-[min(560px,calc(100vw-4rem))] max-w-none rounded-lg px-8 py-8"
        >
          <div className="flex size-11 items-center justify-center rounded-full bg-red-50 text-destructive">
            <FileWarning className="size-5" aria-hidden />
          </div>
          <DialogHeader className="mt-5">
            <DialogTitle className="text-title font-normal">
              Scanned PDF not supported
            </DialogTitle>
          </DialogHeader>
          <p className="mt-3 font-sans text-nav font-ui text-ink-muted">
            <span className="font-medium text-ink">
              {ingestionFailure?.filename}
            </span>{" "}
            does not contain extractable text. Please upload a PDF with
            selectable text.
          </p>
          <div className="mt-7 flex justify-end">
            <Button
              type="button"
              className="rounded-full bg-gray-900 px-6 text-white hover:bg-gray-800"
              onClick={() => setIngestionFailure(null)}
            >
              Got it
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={addAgentOpen} onOpenChange={setAddAgentOpen}>
        <DialogContent className="w-[min(780px,calc(100vw-4rem))] max-w-none rounded-lg px-8 py-10">
          <DialogHeader>
            <DialogTitle className="text-title font-normal">Add agent</DialogTitle>
            <p className="mt-2 font-sans text-nav font-ui text-ink-muted">
              Choose which agents can retrieve from this knowledge base.
            </p>
          </DialogHeader>

          <div className="relative mt-8">
            <Search
              aria-hidden
              className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-ink-placeholder"
            />
            <Input
              value={agentQuery}
              onChange={(event) => setAgentQuery(event.target.value)}
              placeholder="Search"
              className="rounded-full pl-12 focus-visible:ring-gray-300"
            />
          </div>

          <div className="mt-4 min-h-72 max-h-[28rem] overflow-y-auto rounded-xl border border-border">
            {availableAgents.length === 0 ? (
              <p className="px-4 py-8 text-center font-sans text-nav font-ui text-ink-muted">
                {allAgents.length === 0
                  ? "No agents yet. Create one from Agents first."
                  : "No agents match your search."}
              </p>
            ) : (
              availableAgents.map((agent) => {
                const isConnected = connectedAgentIds.has(agent.id);
                const busy = attachingId === agent.id;
                return (
                  <div
                    key={agent.id}
                    className="flex items-center gap-3 border-b border-border px-4 py-3 last:border-b-0"
                  >
                    <span
                      className={cn(
                        "size-8 shrink-0 rounded-full",
                        appearanceClassName(agent.appearance?.key),
                      )}
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-sans text-nav font-ui font-medium text-ink">
                        {agent.name}
                      </p>
                      <p className="truncate font-sans text-nav font-ui text-ink-muted">
                        {agent.description || agent.name}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="pill"
                      className="shrink-0"
                      disabled={busy}
                      onClick={() =>
                        void (isConnected ? onDetach(agent) : onAttach(agent))
                      }
                    >
                      {busy
                        ? isConnected
                          ? "Removing…"
                          : "Connecting…"
                        : isConnected
                          ? "Remove"
                          : "Connect"}
                    </Button>
                  </div>
                );
              })
            )}
          </div>

          <div className="mt-5 flex justify-end">
            <Button
              type="button"
              className="rounded-full bg-gray-900 px-6 text-white hover:bg-gray-800"
              onClick={() => setAddAgentOpen(false)}
              disabled={attachingId != null}
            >
              Done
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {openFile ? (
        <ResourceViewer
          fileId={openFile.id}
          filename={openFile.filename}
          mediaType={openFile.mimeType}
          onClose={() => setOpenFile(null)}
        />
      ) : null}
    </>
  );
}
