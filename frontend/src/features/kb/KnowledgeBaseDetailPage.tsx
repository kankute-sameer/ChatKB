import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Check,
  ChevronDown,
  CloudUpload,
  Loader2,
  Search,
} from "lucide-react";
import { ActionsMenu } from "@/components/ActionsMenu";
import { FileTypeIcon } from "@/components/FileTypeIcon";
import { ResourceViewer } from "@/components/ResourceViewer";
import { ResourceTable, type ResourceColumn } from "@/components/ResourceTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { useCollectionList } from "@/features/kb/useCollectionList";
import { cn } from "@/lib/utils";
import {
  deleteFile,
  formatBytes,
  formatRelativeDate,
  getCollection,
  listFiles,
  uploadFile,
  type Collection,
  type FileStatus,
  type KbFile,
} from "@/lib/kb";

const SUPPORTED_FILE_PATTERN = /\.(pdf|docx|txt|md|csv|tsv|json)$/i;
const ACCEPTED_FILE_TYPES = ".pdf,.docx,.txt,.md,.csv,.tsv,.json";

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
  const [collection, setCollection] = useState<Collection | null>(null);
  const [missing, setMissing] = useState(false);
  const [files, setFiles] = useState<KbFile[]>([]);
  const [query, setQuery] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openFile, setOpenFile] = useState<KbFile | null>(null);

  useEffect(() => {
    setOpenFile(null);
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
        const [latest, rows] = await Promise.all([
          getCollection(id),
          listFiles(id),
        ]);
        if (cancelled) return;
        setCollection(latest);
        setFiles(rows);
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

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return files;
    return files.filter((file) => file.filename.toLowerCase().includes(needle));
  }, [files, query]);

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

  const fileColumns: ResourceColumn<KbFile>[] = [
    {
      id: "name",
      header: "Name",
      className: "w-[42%]",
      render: (row) => (
        <div className="flex min-w-0 items-center gap-3">
          <FileTypeIcon filename={row.filename} className="size-8" />
          <span className="truncate font-normal text-foreground">{row.filename}</span>
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

          {error ? <p className="text-destructive">{error}</p> : null}

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
        </div>
      </div>
      </div>
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
