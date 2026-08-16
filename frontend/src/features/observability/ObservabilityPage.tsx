import { useEffect, useMemo, useState } from "react";
import { Activity, Database, Search } from "lucide-react";
import { FileTypeIcon } from "@/components/FileTypeIcon";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCollectionList } from "@/features/kb/useCollectionList";
import {
  getCollectionIndex,
  getFile,
  listFiles,
  queryCollection,
  type KbFile,
  type ObservabilityQueryHit,
} from "@/lib/kb";
import { cn } from "@/lib/utils";

export function ObservabilityPage() {
  const collections = useCollectionList();
  const [collectionId, setCollectionId] = useState("");
  const [files, setFiles] = useState<KbFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selectedFile, setSelectedFile] = useState<KbFile | null>(null);
  const [collectionIndex, setCollectionIndex] = useState("");
  const [artifact, setArtifact] = useState("content");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ObservabilityQueryHit[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingArtifact, setLoadingArtifact] = useState(false);
  const [loadingIndex, setLoadingIndex] = useState(false);
  const [querying, setQuerying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!collections.length) {
      setCollectionId("");
      return;
    }
    if (!collections.some((collection) => collection.id === collectionId)) {
      setCollectionId(collections[0].id);
    }
  }, [collections, collectionId]);

  useEffect(() => {
    if (!collectionId) {
      setFiles([]);
      setSelectedId("");
      setCollectionIndex("");
      return;
    }
    let active = true;
    setLoadingFiles(true);
    setLoadingIndex(true);
    setError(null);
    setResults([]);
    void Promise.all([listFiles(collectionId), getCollectionIndex(collectionId)])
      .then(([rows, index]) => {
        if (!active) return;
        setFiles(rows);
        setCollectionIndex(index.content);
        setSelectedId((current) =>
          rows.some((file) => file.id === current) ? current : (rows[0]?.id ?? ""),
        );
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason, "Could not load files."));
      })
      .finally(() => {
        if (active) {
          setLoadingFiles(false);
          setLoadingIndex(false);
        }
      });
    return () => {
      active = false;
    };
  }, [collectionId]);

  useEffect(() => {
    if (!collectionId || !selectedId) {
      setSelectedFile(null);
      return;
    }
    let active = true;
    setLoadingArtifact(true);
    void getFile(collectionId, selectedId)
      .then((file) => {
        if (active) setSelectedFile(file);
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason, "Could not load generated files."));
      })
      .finally(() => {
        if (active) setLoadingArtifact(false);
      });
    return () => {
      active = false;
    };
  }, [collectionId, selectedId]);

  const selectedCollection = useMemo(
    () => collections.find((collection) => collection.id === collectionId),
    [collections, collectionId],
  );

  const runQuery = async () => {
    const value = query.trim();
    if (!collectionId || !value || querying) return;
    setQuerying(true);
    setError(null);
    try {
      const response = await queryCollection(collectionId, value);
      setResults(response.results);
    } catch (reason) {
      setError(errorMessage(reason, "The collection query failed."));
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="h-full overflow-auto px-8 py-8">
      <div className="flex w-full flex-col gap-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h1 className="font-sans text-nav font-ui font-normal">Observability</h1>
            <Badge variant="secondary">Alice only</Badge>
          </div>
          <label className="flex items-center gap-3 font-sans text-nav font-ui text-ink-muted">
            Knowledge base
            <select
              value={collectionId}
              onChange={(event) => setCollectionId(event.target.value)}
              className="h-10 min-w-64 rounded-full border border-border bg-white px-4 font-sans text-nav font-ui text-ink outline-none focus:ring-2 focus:ring-gray-300"
            >
              {collections.length === 0 ? (
                <option value="">No knowledge bases</option>
              ) : null}
              {collections.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))}
            </select>
          </label>
        </header>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 font-sans text-nav font-ui text-red-700">
            {error}
          </div>
        ) : null}

        <section className="grid min-h-[32rem] grid-cols-1 gap-6 xl:grid-cols-[22rem_minmax(0,1fr)]">
          <div className="overflow-hidden rounded-xl border border-border bg-white">
            <div className="flex items-center gap-2 border-b border-border px-5 py-4">
              <Database className="size-5 text-ink-muted" />
              <h2 className="font-sans text-nav font-ui font-medium">KB files</h2>
              <span className="ml-auto font-sans text-nav font-ui text-ink-placeholder">
                {files.length}
              </span>
            </div>
            <div className="max-h-[38rem] overflow-auto p-2">
              {loadingFiles ? (
                <p className="px-3 py-4 font-sans text-nav font-ui text-ink-muted">
                  Loading files…
                </p>
              ) : files.length === 0 ? (
                <p className="px-3 py-4 font-sans text-nav font-ui text-ink-muted">
                  No files in this knowledge base.
                </p>
              ) : (
                files.map((file) => (
                  <button
                    key={file.id}
                    type="button"
                    onClick={() => setSelectedId(file.id)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left font-sans text-nav font-ui hover:bg-gray-50",
                      selectedId === file.id && "bg-gray-100",
                    )}
                  >
                    <FileTypeIcon filename={file.filename} className="size-8" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-ink">{file.filename}</span>
                      <span className="block capitalize text-ink-placeholder">
                        {file.status}
                      </span>
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="min-w-0 overflow-hidden rounded-xl border border-border bg-white">
            <div className="flex min-h-16 items-center gap-3 border-b border-border px-5 py-4">
              {selectedFile ? (
                <FileTypeIcon filename={selectedFile.filename} className="size-8" />
              ) : (
                <Activity className="size-5 text-ink-muted" />
              )}
              <div className="min-w-0">
                <h2 className="truncate font-sans text-nav font-ui font-medium">
                  {artifact === "index"
                    ? `${selectedCollection?.name ?? "Collection"} / index.md`
                    : (selectedFile?.filename ?? "Generated files")}
                </h2>
                <p className="font-sans text-nav font-ui text-ink-placeholder">
                  {selectedCollection?.name ?? "Select a knowledge base"}
                </p>
              </div>
            </div>
            <Tabs value={artifact} onValueChange={setArtifact} className="p-5">
              <TabsList>
                <TabsTrigger value="content">content.md</TabsTrigger>
                <TabsTrigger value="index">index.md</TabsTrigger>
              </TabsList>
              <ArtifactContent
                value="content"
                loading={loadingArtifact}
                text={selectedFile?.contentMd}
              />
              <ArtifactContent
                value="index"
                loading={loadingIndex}
                text={collectionIndex}
              />
            </Tabs>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-white p-5">
          <div className="mb-4">
            <h2 className="font-sans text-nav font-ui font-medium">Query collection</h2>
            <p className="font-sans text-nav font-ui text-ink-muted">
              Inspect the chunks returned by semantic and keyword retrieval.
            </p>
          </div>
          <form
            className="flex max-w-4xl gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              void runQuery();
            }}
          >
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-ink-placeholder" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Query this knowledge base"
                className="rounded-full pl-12 focus-visible:ring-gray-300"
              />
            </div>
            <Button
              type="submit"
              disabled={!collectionId || !query.trim() || querying}
              className="rounded-full bg-gray-900 px-6 text-white hover:bg-gray-800"
            >
              {querying ? "Querying…" : "Run query"}
            </Button>
          </form>
          <div className="mt-5 grid grid-cols-1 gap-3">
            {results.map((result, index) => (
              <button
                key={result.chunkId}
                type="button"
                onClick={() => {
                  setSelectedId(result.fileId);
                  setArtifact("content");
                }}
                className="rounded-xl border border-border p-4 text-left hover:bg-gray-50"
              >
                <div className="mb-2 flex flex-wrap items-center gap-2 font-sans text-nav font-ui">
                  <span className="font-medium text-ink">#{index + 1}</span>
                  <span className="text-ink">{result.filename}</span>
                  {result.sectionHeader ? (
                    <span className="text-ink-muted">/ {result.sectionHeader}</span>
                  ) : null}
                  {result.page != null ? (
                    <span className="text-ink-placeholder">Page {result.page}</span>
                  ) : null}
                  <span className="ml-auto text-ink-placeholder">
                    Score {result.score.toFixed(4)}
                  </span>
                </div>
                <p className="whitespace-pre-wrap font-sans text-nav font-ui text-ink-muted">
                  {result.text}
                </p>
              </button>
            ))}
            {!querying && results.length === 0 && query.trim() ? (
              <p className="font-sans text-nav font-ui text-ink-muted">
                Run the query to inspect retrieval results.
              </p>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}

function ArtifactContent({
  value,
  loading,
  text,
}: {
  value: string;
  loading: boolean;
  text: string | null | undefined;
}) {
  return (
    <TabsContent
      value={value}
      className="h-[32rem] overflow-auto rounded-xl border border-border bg-gray-50 p-6"
    >
      {loading ? (
        <p className="font-sans text-nav font-ui text-ink-muted">Loading artifact…</p>
      ) : text ? (
        <MarkdownBody text={text} className="font-sans text-nav font-ui text-ink" />
      ) : (
        <p className="font-sans text-nav font-ui text-ink-muted">
          This artifact has not been generated yet.
        </p>
      )}
    </TabsContent>
  );
}

function errorMessage(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}
