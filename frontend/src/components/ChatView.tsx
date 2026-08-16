import type { FormEvent, KeyboardEvent, ReactNode } from "react";
import { Fragment, useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Check,
  Copy,
  FileText,
  Square,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { ActivityTimeline } from "@/components/ActivityTimeline";
import type { DocumentCitationSource } from "@/components/ai-elements/inline-citation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

const CITE_MARKER = /\[cite:[0-9a-fA-F]{8}\]/g;
type MessageFeedback = "up" | "down";
type FeedbackHandler = (
  messageId: string,
  rating: MessageFeedback,
  comment?: string,
) => Promise<void>;

function textForClipboard(raw: string): string {
  return raw.replace(CITE_MARKER, "").replace(/[ \t]+\n/g, "\n").trim();
}

async function writeClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(area);
      return ok;
    } catch {
      return false;
    }
  }
}

function CopyTextButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current != null) window.clearTimeout(timer.current);
    };
  }, []);

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={copied ? "Copied" : "Copy"}
      onClick={() => {
        void (async () => {
          const ok = await writeClipboard(textForClipboard(text));
          if (!ok) return;
          setCopied(true);
          if (timer.current != null) window.clearTimeout(timer.current);
          timer.current = window.setTimeout(() => setCopied(false), 1500);
        })();
      }}
    >
      {copied ? (
        <Check className="size-4 text-gray-400" />
      ) : (
        <Copy className="size-4 text-gray-400" />
      )}
    </Button>
  );
}

interface ComposerProps {
  placeholder?: string;
  initialValue?: string;
  autoFocus?: boolean;
  start?: ReactNode;
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
  onSubmit?: (text: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  onOpenDocument?: (source: DocumentCitationSource) => void;
  onFeedback?: FeedbackHandler;
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
  onSubmit,
  onStop,
  isStreaming,
  disabled,
  onOpenDocument,
  onFeedback,
}: ChatViewProps) {
  const composer = (
    <Composer
      placeholder={placeholder}
      start={composerStart}
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
        onFeedback={onFeedback}
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
  onFeedback,
}: {
  messages: ChatMessage[];
  emptyState?: ReactNode;
  composer: ReactNode;
  composerFooter?: ReactNode;
  isStreaming?: boolean;
  onOpenDocument?: (source: DocumentCitationSource) => void;
  onFeedback?: FeedbackHandler;
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
                    onFeedback={onFeedback}
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
  onFeedback,
}: {
  message: ChatMessage;
  onOpenDocument?: (source: DocumentCitationSource) => void;
  onFeedback?: FeedbackHandler;
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
          <CopyTextButton text={message.content} />
        </div>
      </div>
    );
  }

  return (
    <AssistantTurn
      message={message}
      onOpenDocument={onOpenDocument}
      onFeedback={onFeedback}
    />
  );
}

function AssistantTurn({
  message,
  onOpenDocument,
  onFeedback,
}: {
  message: ChatMessage;
  onOpenDocument?: (source: DocumentCitationSource) => void;
  onFeedback?: FeedbackHandler;
}) {
  const segments = messageSegments(message);
  const streamingMessage = Boolean(message.streaming);
  const hasContent = Boolean(message.content.trim());
  const answerStarted = segments.some((segment) => segment.text.trim());
  const startedAt = useRef<number | null>(null);
  const [seconds, setSeconds] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<MessageFeedback | null>(null);
  const [feedbackPending, setFeedbackPending] = useState(false);
  const [downDialogOpen, setDownDialogOpen] = useState(false);
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

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

  const submitFeedback = async (
    rating: MessageFeedback,
    comment?: string,
  ): Promise<boolean> => {
    if (!onFeedback || feedbackPending || feedback === rating) return false;
    setFeedbackPending(true);
    setFeedbackError(null);
    try {
      await onFeedback(message.id, rating, comment);
      setFeedback(rating);
      return true;
    } catch {
      setFeedbackError("Could not send feedback. Please try again.");
      return false;
    } finally {
      setFeedbackPending(false);
    }
  };

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
          <CopyTextButton text={message.content} />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Good response"
            aria-pressed={feedback === "up"}
            disabled={
              !onFeedback ||
              feedbackPending ||
              streamingMessage ||
              feedback === "up"
            }
            onClick={() => void submitFeedback("up")}
          >
            <ThumbsUp
              className={cn(
                "size-4",
                feedback === "up" ? "fill-current text-green-600" : "text-gray-400",
              )}
            />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Bad response"
            aria-pressed={feedback === "down"}
            disabled={
              !onFeedback ||
              feedbackPending ||
              streamingMessage ||
              feedback === "down"
            }
            onClick={() => {
              setFeedbackError(null);
              setDownDialogOpen(true);
            }}
          >
            <ThumbsDown
              className={cn(
                "size-4",
                feedback === "down" ? "fill-current text-red-600" : "text-gray-400",
              )}
            />
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

      <Dialog
        open={downDialogOpen}
        onOpenChange={(open) => {
          if (feedbackPending) return;
          setDownDialogOpen(open);
          if (!open) {
            setFeedbackComment("");
            setFeedbackError(null);
          }
        }}
      >
        <DialogContent className="w-[min(620px,calc(100vw-4rem))] max-w-none rounded-lg px-8 py-10">
          <DialogHeader>
            <DialogTitle className="text-title font-normal">
              What could be better?
            </DialogTitle>
            <p className="mt-2 font-sans text-nav font-ui text-ink-muted">
              Tell us why this response was not helpful. Your feedback helps
              improve future answers.
            </p>
          </DialogHeader>
          <form
            className="mt-8 flex flex-col gap-5 font-sans text-nav font-ui"
            onSubmit={(event) => {
              event.preventDefault();
              const comment = feedbackComment.trim();
              if (!comment) return;
              void submitFeedback("down", comment).then((sent) => {
                if (!sent) return;
                setDownDialogOpen(false);
                setFeedbackComment("");
              });
            }}
          >
            <label className="flex flex-col gap-2">
              <span className="text-ink">Reason</span>
              <textarea
                value={feedbackComment}
                onChange={(event) => setFeedbackComment(event.target.value)}
                placeholder="What was incorrect, missing, or unclear?"
                rows={5}
                maxLength={2000}
                autoFocus
                className="flex min-h-32 w-full resize-none rounded-lg border border-input bg-background px-3 py-3 font-sans text-nav font-ui text-foreground placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={feedbackPending}
              />
            </label>
            {feedbackError ? (
              <p className="text-destructive">{feedbackError}</p>
            ) : null}
            <div className="flex justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                className="rounded-full"
                disabled={feedbackPending}
                onClick={() => setDownDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="rounded-full bg-gray-900 px-6 text-white hover:bg-gray-800"
                disabled={feedbackPending || !feedbackComment.trim()}
              >
                {feedbackPending ? "Sending…" : "Send feedback"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

