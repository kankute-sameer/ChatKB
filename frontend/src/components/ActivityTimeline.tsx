import { useEffect, useState, type ReactNode } from "react";
import { Brain, CheckCircle, ChevronDown } from "lucide-react";
import { MarkdownBody } from "@/components/MarkdownBody";
import { TwinOrbit } from "@/components/TwinOrbit";
import {
  outputPreview,
  splitThought,
  toolDisplay,
  toolErrorMessage,
  webSearchHits,
  type ActivityItem,
  type WebSearchHit,
} from "@/lib/activity";
import { cn } from "@/lib/utils";

const copyClass = "font-sans text-composer font-light text-ink";

export function ActivityTimeline({
  activity,
  streaming,
  complete,
  summary,
}: {
  activity: ActivityItem[];
  streaming: boolean;
  complete: boolean;
  summary: string;
}) {
  const [open, setOpen] = useState(streaming || !complete);
  const [detailOpen, setDetailOpen] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (streaming) {
      setOpen(true);
      return;
    }
    if (complete) {
      setOpen(false);
      setDetailOpen({});
    }
  }, [streaming, complete]);

  if (!activity.length) return null;

  return (
    <div className="flex flex-col gap-2">
      {streaming ? (
        <div className="flex items-center gap-3">
          <TwinOrbit size={24} />
          <p className={copyClass}>Thinking</p>
        </div>
      ) : complete ? (
        <button
          type="button"
          className="flex items-center gap-2 text-left"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
        >
          <p className={cn(copyClass, "text-ink-placeholder")}>{summary}</p>
        </button>
      ) : null}

      <Collapse open={open || streaming}>
        <div className="flex flex-col pt-2">
          {activity.map((item, index) => {
            const last = index === activity.length - 1;
            const showLine = !last || complete || streaming;
            const rowOpen = streaming
              ? detailOpen[item.id] !== false
              : Boolean(detailOpen[item.id]);
            return (
              <ActivityRow
                key={item.id}
                item={item}
                streaming={streaming}
                showLine={showLine}
                detailOpen={rowOpen}
                onToggle={() =>
                  setDetailOpen((current) => ({
                    ...current,
                    [item.id]: !rowOpen,
                  }))
                }
              />
            );
          })}
          {complete ? (
            <div className="flex items-center gap-3">
              <div className="flex h-[26px] w-4 shrink-0 items-center justify-center">
                <CheckCircle
                  className="size-4 bg-background text-ink-placeholder"
                  strokeWidth={1.5}
                />
              </div>
              <p className={cn(copyClass, "text-ink-placeholder")}>Done</p>
            </div>
          ) : null}
        </div>
      </Collapse>
    </div>
  );
}

function ActivityRow({
  item,
  streaming,
  showLine,
  detailOpen,
  onToggle,
}: {
  item: ActivityItem;
  streaming: boolean;
  showLine: boolean;
  detailOpen: boolean;
  onToggle: () => void;
}) {
  const Icon = item.kind === "thought" ? Brain : toolDisplay(item.toolName).icon;
  const title =
    item.kind === "thought"
      ? splitThought(item.text).title
      : toolDisplay(item.toolName).headline(item.input);
  const thoughtBody =
    item.kind === "thought"
      ? streaming
        ? item.text
        : splitThought(item.text).body
      : "";
  const hits =
    item.kind === "tool" && item.toolName === "web_search"
      ? webSearchHits(item.output)
      : [];
  const error =
    item.kind === "tool" ? toolErrorMessage(item.output) : "";
  const preview =
    item.kind === "tool" && item.toolName !== "web_search"
      ? outputPreview(item.output)
      : "";
  const hasDetail =
    Boolean(thoughtBody) || hits.length > 0 || Boolean(error) || Boolean(preview);

  return (
    <div className="flex items-stretch gap-3">
      <div className="flex w-4 shrink-0 flex-col items-center">
        <button
          type="button"
          className="relative z-10 flex h-[26px] w-4 shrink-0 items-center justify-center bg-background p-0 text-ink-placeholder focus-visible:outline-none"
          aria-label={item.kind === "thought" ? "Toggle thought" : "Toggle tool"}
          onClick={onToggle}
        >
          <Icon className="size-4" strokeWidth={1.5} />
        </button>
        {showLine ? (
          <div aria-hidden className="w-px min-h-6 flex-1 bg-gray-400" />
        ) : null}
      </div>
      <div className="flex min-w-0 flex-1 flex-col pb-4">
        <button
          type="button"
          className="flex h-[26px] min-w-0 items-center gap-2 p-0 text-left focus-visible:outline-none"
          onClick={onToggle}
          aria-expanded={detailOpen}
        >
          <p
            className={cn(
              copyClass,
              "min-w-0 flex-1 truncate text-ink-placeholder",
            )}
          >
            {title}
          </p>
          {hasDetail ? (
            <ChevronDown
              className={cn(
                "size-4 shrink-0 text-ink-placeholder transition-transform duration-enter ease-motion",
                detailOpen ? "rotate-0" : "-rotate-90",
              )}
              strokeWidth={1.5}
            />
          ) : null}
        </button>
        {hasDetail ? (
          <Collapse open={detailOpen}>
            <div className="mt-2">
              {item.kind === "thought" ? (
                <MarkdownBody
                  text={thoughtBody}
                  className={cn(copyClass, "bg-background text-ink-placeholder")}
                />
              ) : hits.length ? (
                <WebSearchHits hits={hits} />
              ) : (
                <p className={cn(copyClass, "text-ink-placeholder")}>
                  {error || preview}
                </p>
              )}
            </div>
          </Collapse>
        ) : null}
      </div>
    </div>
  );
}

function WebSearchHits({ hits }: { hits: WebSearchHit[] }) {
  return (
    <div className="overflow-hidden rounded border border-border bg-background">
      {hits.map((hit) => {
        const date = formatHitDate(hit.publishedDate);
        return (
          <a
            key={hit.url}
            href={hit.url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 border-b border-border px-3 py-2.5 last:border-b-0 hover:bg-gray-50"
          >
            <img
              src={faviconUrl(hit.url)}
              alt=""
              className="size-4 shrink-0 rounded-sm"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-light text-ink-placeholder">
                {hit.title}
              </p>
              <p className="truncate text-xs text-ink-placeholder">
                {hostname(hit.url)}
              </p>
            </div>
            {date ? (
              <p className="shrink-0 text-xs text-ink-placeholder">{date}</p>
            ) : null}
          </a>
        );
      })}
    </div>
  );
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

function formatHitDate(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function Collapse({
  open,
  children,
}: {
  open: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "grid transition-[grid-template-rows] duration-enter ease-motion motion-reduce:transition-none",
        open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
      )}
    >
      <div className="min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}
