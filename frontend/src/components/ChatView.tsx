import type { FormEvent, KeyboardEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
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
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LandingHero } from "@/components/LandingHero";
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
      <ThreadBody messages={messages} emptyState={emptyState} composer={composer} />
    </div>
  );
}

function ThreadBody({
  messages,
  emptyState,
  composer,
}: {
  messages: ChatMessage[];
  emptyState?: ReactNode;
  composer: ReactNode;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

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
  }, [messages]);

  return (
    <>
      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollRef}
          onScroll={updatePin}
          className="h-full overflow-auto px-8 pt-6 pb-16"
        >
          <div className="mx-auto flex max-w-composer flex-col gap-6">
            {messages.length === 0
              ? emptyState
              : messages.map((message) => (
                  <MessageBlock key={message.id} message={message} />
                ))}
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
  const isUser = message.role === "user";

  return (
    <div className={cn("group flex flex-col gap-2", isUser && "items-end")}>
      {message.thought ? (
        <p className="text-xs text-muted-foreground">{message.thought}</p>
      ) : null}
      <div
        className={cn(
          "max-w-full",
          threadCopyClass,
          isUser && "rounded bg-gray-100 px-4 py-2",
        )}
      >
        {message.content}
      </div>
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
      <div className="flex items-center gap-1 opacity-0 transition-opacity duration-color ease-out group-hover:opacity-100 group-focus-within:opacity-100">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Copy"
          onClick={() => void navigator.clipboard.writeText(message.content)}
        >
          <Copy className="size-4 text-gray-400" />
        </Button>
        {isUser ? null : (
          <>
            <Button variant="ghost" size="icon" aria-label="Good response">
              <ThumbsUp className="size-4 text-gray-400" />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Bad response">
              <ThumbsDown className="size-4 text-gray-400" />
            </Button>
          </>
        )}
      </div>
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
