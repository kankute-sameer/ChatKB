import type { FormEvent, KeyboardEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Brain,
  CheckCircle,
  Copy,
  FileText,
  Mic,
  Plus,
  Square,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LandingHero } from "@/components/LandingHero";
import { MarkdownBody } from "@/components/MarkdownBody";
import { TwinOrbit } from "@/components/TwinOrbit";
import type { ChatMessage } from "@/mocks/data";
import { cn } from "@/lib/utils";

interface ComposerProps {
  placeholder: string;
  start?: ReactNode;
  showMic?: boolean;
  onSubmit?: (text: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
}

export function Composer({
  placeholder,
  start,
  showMic = true,
  onSubmit,
  onStop,
  isStreaming = false,
  disabled = false,
}: ComposerProps) {
  const [text, setText] = useState("");

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled || isStreaming) return;
    onSubmit?.(trimmed);
    setText("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      onSubmit={submit}
      className="rounded-lg border border-border bg-background px-composer py-4 shadow-soft"
    >
      <textarea
        rows={2}
        placeholder={placeholder}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        className="w-full bg-transparent text-composer font-sans font-light text-ink placeholder:text-ink-placeholder focus-visible:outline-none"
      />
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-1">{start}</div>
        <div className="flex items-center gap-1">
          {showMic ? (
            <Button type="button" variant="ghost" size="icon" aria-label="Voice">
              <Mic className="size-icon text-ink-muted" />
            </Button>
          ) : null}
          {isStreaming ? (
            <Button
              type="button"
              size="icon"
              className="rounded-full bg-gray-700 text-white hover:bg-gray-800"
              aria-label="Stop"
              onClick={onStop}
            >
              <Square className="size-3 fill-current" />
            </Button>
          ) : (
            <Button
              type="submit"
              size="icon"
              className="rounded-full bg-gray-700 text-white hover:bg-gray-800"
              aria-label="Send"
              disabled={disabled}
            >
              <ArrowUp className="size-icon" />
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}

/** Same type as sidebar conversation names. */
const titleClass = "font-sans text-nav font-ui text-ink";
/** Same type as the composer while you type. */
const threadCopyClass = "font-sans text-composer font-light text-ink";

interface ChatViewProps {
  messages: ChatMessage[];
  placeholder?: string;
  title?: string;
  header?: ReactNode;
  emptyState?: ReactNode;
  layout?: "landing" | "thread";
  composerStart?: ReactNode;
  showMic?: boolean;
  onSubmit?: (text: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
}

export function ChatView({
  messages,
  placeholder = "Ask anything...",
  title,
  header,
  emptyState,
  layout = "thread",
  composerStart,
  showMic = true,
  onSubmit,
  onStop,
  isStreaming,
  disabled,
}: ChatViewProps) {
  const composer = (
    <Composer
      placeholder={placeholder}
      start={composerStart}
      showMic={showMic}
      onSubmit={onSubmit}
      onStop={onStop}
      isStreaming={isStreaming}
      disabled={disabled}
    />
  );

  if (layout === "landing") {
    return (
      <LandingHero
        title={
          emptyState ?? (
            <h1 className="text-center font-serif text-hero font-hero text-ink">
              What can your agents help with?
            </h1>
          )
        }
        composer={composer}
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      {title ? (
        <div className="px-8 pt-6 pb-2">
          <p className={cn("truncate", titleClass)}>{title}</p>
        </div>
      ) : null}
      {header ? (
        <div className="border-b border-border px-4 py-2">{header}</div>
      ) : null}
      <ThreadBody
        messages={messages}
        emptyState={emptyState}
        composer={composer}
        isStreaming={isStreaming}
      />
    </div>
  );
}

function ThreadBody({
  messages,
  emptyState,
  composer,
  isStreaming,
}: {
  messages: ChatMessage[];
  emptyState?: ReactNode;
  composer: ReactNode;
  isStreaming?: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

  const last = messages[messages.length - 1];
  const waitingForText =
    Boolean(isStreaming) &&
    (!last ||
      last.role === "user" ||
      (last.role === "assistant" && !last.content.trim()));
  const hideEmptyAssistant =
    waitingForText && last?.role === "assistant" && !last.thought;
  const visibleMessages = hideEmptyAssistant
    ? messages.slice(0, -1)
    : messages;

  const updatePin = () => {
    const el = scrollRef.current;
    if (!el) return;
    const away = el.scrollHeight - el.scrollTop - el.clientHeight > 80;
    pinnedRef.current = !away;
    setShowJump(away);
  };

  const scrollToLatest = () => {
    pinnedRef.current = true;
    setShowJump(false);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    bottomRef.current?.scrollIntoView({
      block: "end",
      behavior: reduce ? "auto" : "smooth",
    });
  };

  useEffect(() => {
    if (pinnedRef.current) {
      bottomRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages, waitingForText]);

  return (
    <>
      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollRef}
          onScroll={updatePin}
          className="h-full overflow-auto px-8 pt-6 pb-16"
        >
          <div className="mx-auto flex max-w-composer flex-col gap-6">
            {visibleMessages.length === 0
              ? emptyState
              : visibleMessages.map((message) => (
                  <MessageBlock key={message.id} message={message} />
                ))}
            {waitingForText && !last?.thought ? <TwinOrbit size={24} /> : null}
          </div>
          <div ref={bottomRef} />
        </div>
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-background to-transparent"
        />
        {showJump ? (
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label="Scroll to latest"
            onClick={scrollToLatest}
            className="absolute bottom-4 left-1/2 z-10 -translate-x-1/2 rounded-full bg-background shadow-soft"
          >
            <ArrowDown className="size-icon text-ink" />
          </Button>
        ) : null}
      </div>
      <div className="px-8 pb-4 pt-0">
        <div className="mx-auto max-w-composer">{composer}</div>
      </div>
    </>
  );
}

function MessageBlock({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="group flex flex-col items-end gap-2">
        <div
          className={cn(
            "max-w-full rounded bg-gray-100 px-4 py-2",
            threadCopyClass,
          )}
        >
          {message.content}
        </div>
        <div className="flex items-center gap-1 opacity-0 transition-opacity duration-color ease-out group-hover:opacity-100 group-focus-within:opacity-100">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Copy"
            onClick={() => void navigator.clipboard.writeText(message.content)}
          >
            <Copy className="size-4 text-gray-400" />
          </Button>
        </div>
      </div>
    );
  }

  return <AssistantTurn message={message} />;
}

function splitThought(text: string): { title: string; body: string } {
  const trimmed = text.trim();
  const heading = trimmed.match(/^\*\*(.+?)\*\*\s*(?:\n+([\s\S]*))?$/);
  if (heading) {
    return { title: heading[1], body: heading[2]?.trim() ?? "" };
  }
  const [first, ...rest] = trimmed.split(/\n+/);
  const title = first.replace(/^\*\*|\*\*$/g, "").trim() || "Thought";
  if (rest.length) {
    return { title, body: rest.join("\n\n").trim() };
  }
  if (title.length <= 80) {
    return { title, body: "" };
  }
  return { title: "Thought", body: trimmed };
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

function AssistantTurn({ message }: { message: ChatMessage }) {
  const streaming = Boolean(message.thoughtStreaming);
  const hasThought = Boolean(message.thought?.trim());
  const hasContent = Boolean(message.content.trim());
  const { title, body } = splitThought(message.thought ?? "");

  const [thoughtOpen, setThoughtOpen] = useState(true);
  const [detailOpen, setDetailOpen] = useState(true);
  const startedAt = useRef<number | null>(null);
  const [seconds, setSeconds] = useState<number | null>(null);

  useEffect(() => {
    if (streaming) {
      startedAt.current ??= Date.now();
      setThoughtOpen(true);
      setDetailOpen(true);
      return;
    }
    if (startedAt.current != null) {
      setSeconds(Math.max(1, Math.round((Date.now() - startedAt.current) / 1000)));
      setDetailOpen(false);
    }
  }, [streaming]);

  const thoughtLabel =
    seconds != null ? `Thought for ${seconds}s` : "Thought";

  return (
    <div className="group flex max-w-full flex-col gap-2 bg-background">
      {streaming ? (
        <div className="flex items-center gap-3">
          <TwinOrbit size={24} />
          <p className={threadCopyClass}>Thinking</p>
        </div>
      ) : hasThought ? (
        <button
          type="button"
          className="flex items-center gap-2 text-left"
          onClick={() => setThoughtOpen((open) => !open)}
          aria-expanded={thoughtOpen}
        >
          <p className={cn(threadCopyClass, "text-ink-placeholder")}>
            {thoughtLabel}
          </p>
        </button>
      ) : null}

      {hasThought ? (
        <Collapse open={thoughtOpen || streaming}>
          <div className="flex items-stretch gap-3 pt-2">
            <div className="flex w-4 shrink-0 flex-col items-center">
              <button
                type="button"
                className="relative z-10 shrink-0 bg-background text-ink-placeholder focus-visible:outline-none"
                aria-label="Toggle thought"
                onClick={() => setDetailOpen((open) => !open)}
              >
                <Brain className="size-4" strokeWidth={1.5} />
              </button>
              <div
                aria-hidden
                className="my-2 w-px min-h-6 flex-1 bg-gray-400"
              />
              {!streaming ? (
                <CheckCircle
                  className="relative z-10 size-4 shrink-0 bg-background text-ink-placeholder"
                  strokeWidth={1.5}
                />
              ) : null}
            </div>
            <div className="flex min-w-0 flex-1 flex-col">
              <button
                type="button"
                className="flex min-w-0 items-start gap-2 text-left focus-visible:outline-none"
                onClick={() => setDetailOpen((open) => !open)}
                aria-expanded={detailOpen}
              >
                <p
                  className={cn(
                    threadCopyClass,
                    "min-w-0 flex-1 font-medium text-ink-placeholder",
                  )}
                >
                  {title}
                </p>
              </button>
              <Collapse open={detailOpen}>
                <div className="mt-2">
                  <MarkdownBody
                    text={streaming ? (message.thought ?? "") : body}
                    className={cn(
                      threadCopyClass,
                      "bg-background text-ink-placeholder",
                    )}
                  />
                </div>
              </Collapse>
              {!streaming ? (
                <p
                  className={cn(
                    threadCopyClass,
                    "mt-auto pt-6 text-ink-placeholder",
                  )}
                >
                  Done
                </p>
              ) : null}
            </div>
          </div>
        </Collapse>
      ) : null}

      {hasContent ? (
        <div className={cn("min-w-0", threadCopyClass)}>
          <MarkdownBody text={message.content} />
        </div>
      ) : null}

      {hasContent ? (
        <div className="flex items-center gap-1 opacity-0 transition-opacity duration-color ease-out group-hover:opacity-100 group-focus-within:opacity-100">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Copy"
            onClick={() => void navigator.clipboard.writeText(message.content)}
          >
            <Copy className="size-4 text-gray-400" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Good response">
            <ThumbsUp className="size-4 text-gray-400" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Bad response">
            <ThumbsDown className="size-4 text-gray-400" />
          </Button>
        </div>
      ) : null}

      {message.citations?.length ? (
        <div className="flex flex-wrap gap-2">
          {message.citations.map((citation) => (
            <Badge key={citation.id} variant="outline" className="gap-1">
              <FileText className="size-3" />
              {citation.label}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function ComposerStartDefault() {
  return (
    <Button type="button" variant="ghost" size="icon" aria-label="Add">
      <Plus className="size-icon text-ink" />
    </Button>
  );
}
