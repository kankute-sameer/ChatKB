import { type ComponentProps, useState } from "react";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { FileText } from "lucide-react";
import { cn } from "@/lib/utils";

export interface WebCitationSource {
  type?: "source-url";
  sourceId: string;
  url: string;
  title?: string;
  snippet?: string;
  publishedDate?: string | null;
}

export interface DocumentCitationSource {
  type: "source-document";
  sourceId: string;
  fileId: string;
  filename: string;
  page: number;
  anchor: string;
  bbox: number[];
  regions?: number[][];
  collectionId: string;
  snippet?: string;
}

export type CitationSource = WebCitationSource | DocumentCitationSource;

export type InlineCitationProps = ComponentProps<"span">;

export function InlineCitation({ className, ...props }: InlineCitationProps) {
  return <span className={cn("inline-flex align-middle", className)} {...props} />;
}

export function InlineCitationCard(props: ComponentProps<typeof HoverCard>) {
  return <HoverCard openDelay={150} closeDelay={200} {...props} />;
}

export type InlineCitationCardTriggerProps = ComponentProps<"button"> & {
  sources: CitationSource[];
  activeSource?: CitationSource;
  onOpenDocument?: (source: DocumentCitationSource) => void;
};

export function InlineCitationCardTrigger({
  sources,
  activeSource,
  onOpenDocument,
  className,
  ...props
}: InlineCitationCardTriggerProps) {
  const first = activeSource ?? sources[0];
  if (!first) return null;
  const document = isDocumentSource(first);
  const label = document ? first.filename : hostname(first.url);
  const extra = sources.length > 1 ? ` +${sources.length - 1}` : "";

  return (
    <HoverCardTrigger asChild>
      <button
        type="button"
        className={cn(
          "mx-0.5 inline-flex max-w-[12rem] items-center gap-1.5 rounded-full border border-border bg-gray-50 px-1 py-1 align-middle text-xs leading-none text-ink-muted hover:bg-gray-100",
          className,
        )}
        onClick={(event) => {
          event.preventDefault();
          if (document) {
            onOpenDocument?.(first);
          } else {
            window.open(first.url, "_blank", "noopener,noreferrer");
          }
        }}
        {...props}
      >
        {document ? (
          <FileText className="size-3 shrink-0" />
        ) : (
          <img
            src={faviconUrl(first.url)}
            alt=""
            className="size-3 shrink-0 rounded-sm"
          />
        )}
        <span className="truncate">{label}{extra}</span>
      </button>
    </HoverCardTrigger>
  );
}

export function InlineCitationCardBody({
  className,
  ...props
}: ComponentProps<"div">) {
  return <div className={cn("flex flex-col gap-2", className)} {...props} />;
}

export function InlineCitationSource({
  title,
  url,
  description,
  className,
  ...props
}: ComponentProps<"div"> & {
  title?: string;
  url?: string;
  description?: string;
}) {
  return (
    <div className={cn("flex min-w-0 gap-2", className)} {...props}>
      {url ? (
        <img
          src={faviconUrl(url)}
          alt=""
          className="mt-0.5 size-4 shrink-0 rounded-sm"
        />
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {title ? (
          <p className="truncate font-medium text-ink">{title}</p>
        ) : null}
        {description ? (
          <p className="line-clamp-3 text-xs text-ink-muted">{description}</p>
        ) : null}
        {url ? (
          <p className="truncate text-xs text-ink-placeholder">{hostname(url)}</p>
        ) : null}
      </div>
    </div>
  );
}

export function CitationChip({
  sources,
  onOpenDocument,
}: {
  sources: CitationSource[];
  onOpenDocument?: (source: DocumentCitationSource) => void;
}) {
  const [index, setIndex] = useState(0);
  const resolved = sources.filter((source) =>
    isDocumentSource(source) ? Boolean(source.filename) : Boolean(source.url),
  );
  if (resolved.length === 0) return null;

  const current = resolved[Math.min(index, resolved.length - 1)] ?? resolved[0];

  return (
    <InlineCitation>
      <InlineCitationCard>
        <InlineCitationCardTrigger
          sources={resolved}
          activeSource={current}
          onOpenDocument={onOpenDocument}
        />
        <HoverCardContent side="top" className="w-[320px]">
          <InlineCitationCardBody>
            {resolved.length > 1 ? (
              <div className="flex items-center justify-between text-xs text-ink-placeholder">
                <button
                  type="button"
                  className="hover:text-ink"
                  onClick={() =>
                    setIndex((value) =>
                      value === 0 ? resolved.length - 1 : value - 1,
                    )
                  }
                >
                  Prev
                </button>
                <span>
                  {index + 1}/{resolved.length}
                </span>
                <button
                  type="button"
                  className="hover:text-ink"
                  onClick={() =>
                    setIndex((value) => (value + 1) % resolved.length)
                  }
                >
                  Next
                </button>
              </div>
            ) : null}
            {isDocumentSource(current) ? (
              <div className="flex min-w-0 gap-2">
                <FileText className="mt-0.5 size-4 shrink-0 text-ink-muted" />
                <div className="min-w-0">
                  <p className="truncate font-medium text-ink">
                    {current.filename}
                  </p>
                  <p className="text-xs text-ink-placeholder">
                    page {current.page}
                  </p>
                  {current.snippet ? (
                    <p className="mt-1 line-clamp-3 text-xs text-ink-muted">
                      {current.snippet}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : (
              <a
                href={current.url}
                target="_blank"
                rel="noreferrer"
                className="block rounded hover:bg-gray-50"
              >
                <InlineCitationSource
                  title={current.title}
                  url={current.url}
                  description={current.snippet}
                />
              </a>
            )}
          </InlineCitationCardBody>
        </HoverCardContent>
      </InlineCitationCard>
    </InlineCitation>
  );
}

function isDocumentSource(
  source: CitationSource,
): source is DocumentCitationSource {
  return source.type === "source-document";
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function faviconUrl(url: string): string {
  try {
    return `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=32`;
  } catch {
    return "";
  }
}
