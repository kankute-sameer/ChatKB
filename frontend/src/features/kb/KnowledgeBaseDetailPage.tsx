import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FileText, Loader2, Upload } from "lucide-react";
import { ActionsMenu } from "@/components/ActionsMenu";
import { ResourceTable, type ResourceColumn } from "@/components/ResourceTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  deleteFile,
  formatBytes,
  formatDate,
  getCollection,
  listFiles,
  uploadFile,
  type Collection,
  type FileStatus,
  type KbFile,
} from "@/lib/kb";

function StatusBadge({ status, error }: { status: FileStatus; error: string | null }) {
  if (status === "processing") {
    return (
      <Badge variant="warning" className="gap-1">
        <Loader2 className="size-3 animate-spin" />
        Processing
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge variant="danger" title={error ?? undefined}>
        Failed
      </Badge>
    );
  }
  return <Badge variant="success">Ready</Badge>;
}

export function KnowledgeBaseDetailPage() {
  const { id } = useParams();
  const inputRef = useRef<HTMLInputElement>(null);
  const [collection, setCollection] = useState<Collection | null>(null);
  const [missing, setMissing] = useState(false);
  const [files, setFiles] = useState<KbFile[]>([]);
  const [query, setQuery] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    const pdfs = Array.from(list).filter(
      (file) =>
        file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"),
    );
    if (pdfs.length === 0) {
      setError("Only PDF files are supported");
      return;
    }
    setError(null);
    setUploading(true);
    try {
      for (const file of pdfs) {
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
      render: (row) => (
        <div className="flex items-center gap-3">
          <FileText className="size-4 text-gray-500" />
          <span className="font-medium">{row.filename}</span>
        </div>
      ),
    },
    {
      id: "size",
      header: "Size",
      render: (row) => formatBytes(row.sizeBytes),
    },
    {
      id: "status",
      header: "Status",
      render: (row) => <StatusBadge status={row.status} error={row.error} />,
    },
    {
      id: "addedAt",
      header: "Added",
      render: (row) => formatDate(row.createdAt),
    },
    {
      id: "actions",
      header: "",
      className: "w-8",
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
      <div className="p-8 text-sm text-muted-foreground">
        Knowledge base not found.{" "}
        <Link to="/kb" className="text-accent">
          Back
        </Link>
      </div>
    );
  }

  if (!collection) {
    return (
      <div className="p-8 text-sm text-muted-foreground">Loading…</div>
    );
  }

  return (
    <div className="h-full overflow-auto px-8 py-8">
      <div className="mx-auto flex max-w-content flex-col gap-6">
        <div>
          <Link to="/kb" className="text-xs text-muted-foreground">
            Knowledge base
          </Link>
          <h1 className="mt-2 text-lg font-medium">{collection.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {collection.description || "Files in this collection."}
          </p>
        </div>

        <Tabs defaultValue="files">
          <TabsList>
            <TabsTrigger value="files">Files ({files.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="files">
            <div className="flex flex-col gap-4">
              <div
                className={cn(
                  "flex flex-col items-center justify-center gap-2 rounded border border-dashed border-border px-6 py-8 text-sm text-muted-foreground",
                  dragOver && "border-accent bg-accent-muted",
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
                <Upload className="size-5 text-gray-400" />
                <p>Drop PDFs here or</p>
                <Button
                  type="button"
                  variant="outline"
                  disabled={uploading}
                  onClick={() => inputRef.current?.click()}
                >
                  {uploading ? "Uploading…" : "Choose files"}
                </Button>
                <input
                  ref={inputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  multiple
                  className="hidden"
                  onChange={(event) => {
                    if (event.target.files) void onUpload(event.target.files);
                    event.target.value = "";
                  }}
                />
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search files"
              />
              <ResourceTable
                rows={visible}
                columns={fileColumns}
                getRowId={(row) => row.id}
                emptyMessage="No files yet. Upload a PDF to ingest it."
              />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
