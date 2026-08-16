import { useRef, useState, type FormEvent } from "react";
import { CloudUpload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  createCollection,
  notifyCollectionsChanged,
  uploadFile,
} from "@/lib/kb";

interface CreateKnowledgeBaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (collectionId: string) => void;
}

const SUPPORTED_FILE_PATTERN = /\.(pdf|docx|txt|md|csv|tsv|json)$/i;
const ACCEPTED_FILE_TYPES = ".pdf,.docx,.txt,.md,.csv,.tsv,.json";

function isSupportedFile(file: File): boolean {
  return SUPPORTED_FILE_PATTERN.test(file.name);
}

export function CreateKnowledgeBaseDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateKnowledgeBaseDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setName("");
    setDescription("");
    setFiles([]);
    setDragOver(false);
    setError(null);
  };

  const addFiles = (list: FileList | File[]) => {
    const accepted = Array.from(list).filter(isSupportedFile);
    if (accepted.length === 0) {
      setError("Choose a PDF, DOCX, TXT, MD, CSV, TSV, or JSON file");
      return;
    }
    setError(null);
    setFiles((current) => {
      const seen = new Set(current.map((file) => `${file.name}:${file.size}`));
      const next = [...current];
      for (const file of accepted) {
        const key = `${file.name}:${file.size}`;
        if (!seen.has(key)) {
          seen.add(key);
          next.push(file);
        }
      }
      return next;
    });
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || creating) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createCollection({
        name: trimmed,
        description: description.trim(),
      });
      for (const file of files) {
        await uploadFile(created.id, file);
      }
      notifyCollectionsChanged();
      reset();
      onOpenChange(false);
      onCreated(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent className="w-[min(780px,calc(100vw-4rem))] max-w-none rounded-lg px-8 py-10">
        <DialogHeader>
          <DialogTitle className="text-title font-normal">
            Create knowledge base
          </DialogTitle>
        </DialogHeader>
        <form
          className="mt-8 flex flex-col gap-6 font-sans text-nav font-ui"
          onSubmit={(event) => void onSubmit(event)}
        >
          <label className="flex flex-col gap-2">
            <span className="text-foreground">Name</span>
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Partner integration notes"
              className="rounded-lg focus-visible:ring-gray-300"
              autoFocus
            />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-foreground">Description</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What's in this knowledge base?"
              rows={5}
              className="flex min-h-32 w-full resize-none rounded-lg border border-input bg-background px-3 py-3 font-sans text-nav font-ui text-foreground placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </label>

          <div className="flex flex-col gap-2">
            <span className="text-foreground">Files</span>
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
                addFiles(event.dataTransfer.files);
              }}
            >
              <CloudUpload className="size-5 shrink-0 text-gray-400" />
              <p className="min-w-0 flex-1 text-muted-foreground">
                Drag and drop PDF, DOCX, TXT, MD, CSV, TSV, or JSON files
              </p>
              <Button
                type="button"
                className="shrink-0 rounded-full bg-gray-900 text-white hover:bg-gray-800"
                onClick={() => inputRef.current?.click()}
              >
                Browse files
              </Button>
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPTED_FILE_TYPES}
                multiple
                className="hidden"
                onChange={(event) => {
                  if (event.target.files) addFiles(event.target.files);
                  event.target.value = "";
                }}
              />
            </div>
            {files.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {files.map((file) => (
                  <li
                    key={`${file.name}:${file.size}`}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2"
                  >
                    <span className="min-w-0 truncate">{file.name}</span>
                    <button
                      type="button"
                      className="shrink-0 text-gray-400 hover:text-foreground"
                      onClick={() =>
                        setFiles((current) =>
                          current.filter(
                            (row) =>
                              `${row.name}:${row.size}` !==
                              `${file.name}:${file.size}`,
                          ),
                        )
                      }
                    >
                      <X className="size-4" />
                      <span className="sr-only">Remove {file.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          {error ? <p className="text-destructive">{error}</p> : null}

          <div className="mt-2 flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              className="rounded-full"
              onClick={() => {
                reset();
                onOpenChange(false);
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={creating || !name.trim()}
              className="rounded-full bg-gray-500 text-white hover:bg-gray-600 disabled:opacity-50"
            >
              {creating ? "Creating…" : "Create"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
