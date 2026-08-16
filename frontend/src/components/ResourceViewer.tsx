import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import Papa from "papaparse";
import { DocumentViewer } from "@/components/DocumentViewer";
import { FileTypeIcon } from "@/components/FileTypeIcon";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface FileView {
  filename: string;
  mimeType: string;
  content: string;
  pageCount: number | null;
}

export interface ResourceViewerProps {
  fileId: string;
  filename: string;
  mediaType?: string;
  page?: number;
  bbox?: number[];
  regions?: number[][];
  onClose: () => void;
}

export function ResourceViewer(props: ResourceViewerProps) {
  if (props.mediaType === "application/pdf" || props.filename.endsWith(".pdf")) {
    return <DocumentViewer {...props} />;
  }
  return <TextResourceViewer {...props} />;
}

function TextResourceViewer({
  fileId,
  filename,
  page,
  onClose,
}: ResourceViewerProps) {
  const [file, setFile] = useState<FileView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setFile(null);
    setError(null);
    void api<FileView>(`/v1/files/${encodeURIComponent(fileId)}/view`)
      .then((result) => {
        if (active) setFile(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Could not load this file.");
        }
      });
    return () => {
      active = false;
    };
  }, [fileId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const extension = filename.split(".").pop()?.toLowerCase();
  const renderMarkdown = extension === "md" || extension === "markdown" || extension === "docx";
  const renderTable = extension === "csv" || extension === "tsv";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={filename}
      className="fixed inset-y-0 right-0 z-[70] flex w-full flex-col border-l border-border bg-gray-100 shadow-2xl md:w-[clamp(36rem,60vw,64rem)]"
    >
      <div className="flex items-center gap-3 border-b border-border bg-white px-4 py-3 text-ink">
        <FileTypeIcon filename={filename} className="size-8" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-sans text-nav font-ui font-medium">{filename}</p>
          <p className="font-sans text-nav font-ui text-ink-muted">
            {page != null
              ? `Page ${page}`
              : file?.pageCount
                ? `${file.pageCount} pages`
                : "Full file"}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Close document"
          onClick={onClose}
        >
          <X className="size-5" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-6">
        <article className="mx-auto min-h-full max-w-4xl rounded-xl bg-white p-8 shadow-sm">
          {!file && !error ? (
            <p className="font-sans text-nav font-ui text-ink-muted">Loading file…</p>
          ) : error ? (
            <p className="font-sans text-nav font-ui text-red-700">{error}</p>
          ) : renderMarkdown ? (
            <MarkdownBody
              text={file?.content ?? ""}
              className="font-sans text-nav font-ui text-ink"
            />
          ) : renderTable ? (
            <DelimitedTable
              content={file?.content ?? ""}
              delimiter={extension === "tsv" ? "\t" : ","}
            />
          ) : (
            <pre className="whitespace-pre-wrap break-words font-mono text-nav leading-7 text-ink">
              {file?.content}
            </pre>
          )}
        </article>
      </div>
    </div>
  );
}

function DelimitedTable({
  content,
  delimiter,
}: {
  content: string;
  delimiter: "," | "\t";
}) {
  const rows = useMemo(
    () =>
      Papa.parse<string[]>(content, {
        delimiter,
        skipEmptyLines: true,
      }).data,
    [content, delimiter],
  );
  const [header = [], ...body] = rows;

  if (header.length === 0) {
    return <p className="font-sans text-nav font-ui text-ink-muted">This file is empty.</p>;
  }

  return (
    <div className="overflow-auto rounded-xl border border-border">
      <table className="w-max min-w-full border-collapse font-sans text-nav font-ui">
        <thead className="sticky top-0 z-10 bg-gray-100">
          <tr>
            {header.map((cell, index) => (
              <th
                key={`${cell}-${index}`}
                scope="col"
                className="whitespace-nowrap border-b border-r border-border px-4 py-3 text-left font-medium text-ink last:border-r-0"
              >
                {cell || `Column ${index + 1}`}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={rowIndex} className="odd:bg-white even:bg-gray-50">
              {header.map((_, columnIndex) => (
                <td
                  key={columnIndex}
                  className="max-w-[32rem] whitespace-pre-wrap border-b border-r border-border px-4 py-3 align-top text-ink last:border-r-0"
                >
                  {row[columnIndex] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
