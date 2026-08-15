import type { FormEvent, KeyboardEvent, ReactNode } from "react";
import { Fragment, useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Copy,
  FileText,
  Mic,
  Plus,
  Square,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { ActivityTimeline } from "@/components/ActivityTimeline";
import type { DocumentCitationSource } from "@/components/ai-elements/inline-citation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LandingHero } from "@/components/LandingHero";
import { MarkdownBody } from "@/components/MarkdownBody";
import { TwinOrbit } from "@/components/TwinOrbit";
import {
  hasActivity,
  messageSegments,
  segmentSummary,
} from "@/lib/activity";
import type { ChatMessage } from "@/mocks/data";
import { cn } from "@/lib/utils";

interface ComposerProps {
  placeholder?: string;
  initialValue?: string;
  autoFocus?: boolean;
  start?: ReactNode;
  showMic?: boolean;
  onSubmit?: (text: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
}

export function Composer({
  placeholder,
  initialValue = "",
  autoFocus = false,
  start,
  showMic = true,
  onSubmit,
  onStop,
  isStreaming = false,
  disabled = false,
}: ComposerProps) {
  const [text, setText] = useState(initialValue);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!autoFocus) return;
    const el = inputRef.current;
    if (!el) return;
    el.focus();
    const len = el.value.length;
    el.setSelectionRange(len, len);
  }, [autoFocus]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled || isStreaming) return;
    onSubmit?.(trimmed);
    setText(initialValue);
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
        ref={inputRef}
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
  composerFooter?: ReactNode;
  showMic?: boolean;
  onSubmit?: (text: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  onOpenDocument?: (source: DocumentCitationSource) => void;
}

export function ChatView({
  messages,
  placeholder = "Ask anything...",
  title,
  header,
  emptyState,
  layout = "thread",
  composerStart,
  composerFooter,
  showMic = true,
  onSubmit,
  onStop,
  isStreaming,
  disabled,
  onOpenDocument,
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
        composerFooter={composerFooter}
        isStreaming={isStreaming}
        onOpenDocument={onOpenDocument}
      />
    </div>
  );
}

function ThreadBody({
  messages,
  emptyState,
  composer,
  composerFooter,
  isStreaming,
  onOpenDocument,
}: {
  messages: ChatMessage[];
  emptyState?: ReactNode;
  composer: ReactNode;
  composerFooter?: ReactNode;
  isStreaming?: boolean;
  onOpenDocument?: (source: DocumentCitationSource) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

  const last = messages[messages.length - 1];
  const lastSegments = last ? messageSegments(last) : [];
  const lastHasActivity = last?.role === "assistant" && hasActivity(lastSegments);
  const waitingForText =
    Boolean(isStreaming) &&
    (!last ||
      last.role === "user" ||
      (last.role === "assistant" && !last.content.trim()));
  const hideEmptyAssistant =
    waitingForText && last?.role === "assistant" && !lastHasActivity;
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
                  <MessageBlock
                    key={message.id}
                    message={message}
                    onOpenDocument={onOpenDocument}
                  />
                ))}
            {waitingForText && !lastHasActivity ? <TwinOrbit size={24} /> : null}
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
        <div className="mx-auto max-w-composer">
          {composer}
          {composerFooter}
        </div>
      </div>
    </>
  );
}

function MessageBlock({
  message,
  onOpenDocument,
}: {
  message: ChatMessage;
  onOpenDocument?: (source: DocumentCitationSource) => void;
}) {
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

  return <AssistantTurn message={message} onOpenDocument={onOpenDocument} />;
}

function AssistantTurn({
  message,
  onOpenDocument,
}: {
  message: ChatMessage;
  onOpenDocument?: (source: DocumentCitationSource) => void;
}) {
  const segments = messageSegments(message);
  const streamingMessage = Boolean(message.streaming);
  const hasContent = Boolean(message.content.trim());
  const answerStarted = segments.some((segment) => segment.text.trim());
  const startedAt = useRef<number | null>(null);
  const [seconds, setSeconds] = useState<number | null>(null);

  useEffect(() => {
    if (streamingMessage && !answerStarted) {
      startedAt.current ??= Date.now();
      return;
    }
    if (startedAt.current != null) {
      const elapsed = Math.max(
        1,
        Math.round((Date.now() - startedAt.current) / 1000),
      );
      setSeconds((current) => current ?? elapsed);
    }
  }, [streamingMessage, answerStarted]);

  return (
    <div className="group flex max-w-full flex-col gap-2 bg-background">
      {segments.map((segment, index) => {
        const last = index === segments.length - 1;
        const segmentStreaming =
          streamingMessage && last && !segment.text.trim();
        const segmentComplete = Boolean(segment.text.trim());
        return (
          <Fragment key={`${message.id}-${index}`}>
            {segment.activity.length ? (
              <ActivityTimeline
                activity={segment.activity}
                streaming={segmentStreaming}
                complete={segmentComplete}
                summary={segmentSummary(segment.activity, {
                  includeDuration: index === 0,
                  seconds,
                })}
              />
            ) : null}
            {segment.text.trim() ? (
              <div className={cn("min-w-0", threadCopyClass)}>
                <MarkdownBody
                  text={segment.text}
                  sources={message.sources}
                  onOpenDocument={onOpenDocument}
                />
              </div>
            ) : null}
          </Fragment>
        );
      })}

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
