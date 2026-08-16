import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { ChatView } from "@/components/ChatView";
import { ResourceViewer } from "@/components/ResourceViewer";
import type { DocumentCitationSource } from "@/components/ai-elements/inline-citation";
import { getToken } from "@/lib/api";
import { segmentsFromParts } from "@/lib/activity";
import type { ChatMessage } from "@/mocks/data";
import { getAgent, type Agent } from "@/lib/agents";
import { AgentChip } from "@/features/agents/AgentChip";
import {
  getConversation,
  notifyConversationsChanged,
  scoreMessage,
  stoppedStorageKey,
  textFromParts,
  type ConversationDetail,
  type ConversationMessage,
} from "@/lib/conversations";

interface LocationState {
  pendingText?: string;
}

export function ConversationPage() {
  const { id } = useParams();
  const [conversation, setConversation] = useState<ConversationDetail | null>(
    null,
  );
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    getConversation(id)
      .then((detail) => {
        if (!cancelled) setConversation(detail);
      })
      .catch(() => {
        if (!cancelled) setMissing(true);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!id) {
    return null;
  }
  if (missing) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        Conversation not found.{" "}
        <Link to="/" className="text-accent">
          New chat
        </Link>
      </div>
    );
  }
  if (!conversation) {
    return <div className="p-8 text-sm text-muted-foreground">Loading…</div>;
  }

  return (
    <ConversationChat conversation={conversation} showTitle />
  );
}

export function ConversationChat({
  conversation,
  pendingText: pendingTextProp,
  placeholder = "Ask anything...",
  header,
  showTitle = true,
  composerStart,
  composerFooter,
  onSettled,
}: {
  conversation: ConversationDetail;
  pendingText?: string;
  placeholder?: string;
  header?: ReactNode;
  showTitle?: boolean;
  composerStart?: ReactNode;
  composerFooter?: ReactNode;
  onSettled?: () => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const pendingText =
    pendingTextProp ?? (location.state as LocationState | null)?.pendingText;
  const sentPending = useRef(false);
  const [resume, setResume] = useState(
    () => sessionStorage.getItem(stoppedStorageKey(conversation.id)) == null,
  );

  const [title, setTitle] = useState(conversation.title ?? "New chat");
  const [agent, setAgent] = useState<Agent | null>(null);
  const [openDocument, setOpenDocument] =
    useState<DocumentCitationSource | null>(null);

  useEffect(() => {
    if (
      !conversation.targetAgentId ||
      conversation.sessionType === "build"
    ) {
      setAgent(null);
      return;
    }
    let cancelled = false;
    getAgent(conversation.targetAgentId)
      .then((latest) => {
        if (!cancelled) setAgent(latest);
      })
      .catch(() => {
        if (!cancelled) setAgent(null);
      });
    return () => {
      cancelled = true;
    };
  }, [conversation.targetAgentId, conversation.sessionType]);

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        prepareSendMessagesRequest: ({ id, messages }) => ({
          api: "/api/v1/responses",
          body: {
            id,
            message: messages[messages.length - 1],
            stream: true,
            trigger: "submit-message",
          },
          headers: authHeaders(),
        }),
        prepareReconnectToStreamRequest: ({ id }) => ({
          api: `/api/v1/conversations/${id}/stream`,
          headers: authHeaders(),
        }),
      }),
    [],
  );

  const { messages, sendMessage, status, stop } = useChat({
    id: conversation.id,
    messages: toUIMessages(conversation.messages),
    resume,
    transport,
    onError: (error) => {
      if (error.name === "AbortError") return;
      console.error(error);
    },
  });

  useEffect(() => {
    if (!pendingText || sentPending.current) return;
    if (status !== "ready") return;
    sentPending.current = true;
    sessionStorage.removeItem(stoppedStorageKey(conversation.id));
    setResume(true);
    void sendMessage({ text: pendingText });
    navigate(".", { replace: true, state: {} });
    window.setTimeout(() => notifyConversationsChanged(), 1500);
  }, [pendingText, status, sendMessage, navigate, conversation.id]);

  useEffect(() => {
    if (conversation.title) {
      setTitle(conversation.title);
      return;
    }
    let cancelled = false;
    const refresh = () => {
      void getConversation(conversation.id).then((detail) => {
        if (!cancelled && detail.title) {
          setTitle(detail.title);
          notifyConversationsChanged();
        }
      });
    };
    const interval = window.setInterval(refresh, 1500);
    const timeout = window.setTimeout(() => window.clearInterval(interval), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.clearTimeout(timeout);
    };
  }, [conversation.id, conversation.title]);

  const isStreaming = status === "streaming" || status === "submitted";
  const wasStreaming = useRef(false);

  useEffect(() => {
    if (isStreaming) {
      wasStreaming.current = true;
      return;
    }
    if (wasStreaming.current) {
      wasStreaming.current = false;
      onSettled?.();
    }
  }, [isStreaming, onSettled]);

  const displayMessages: ChatMessage[] = messages.map((message, index) => {
    const segments = segmentsFromParts(message.parts);
    const content = segments.map((segment) => segment.text).join("")
      || textFromUIMessage(message);
    const isLast = index === messages.length - 1;
    return {
      id: message.id,
      threadId: conversation.id,
      role: message.role === "user" ? "user" : "assistant",
      content,
      parts: message.parts.map((part) => ({ ...part })),
      segments,
      streaming: isStreaming && isLast && message.role !== "user",
      sources: sourcesFromUIMessage(message),
    };
  });

  const onStop = () => {
    sessionStorage.setItem(stoppedStorageKey(conversation.id), "1");
    setResume(false);
    const last = messages[messages.length - 1];
    void fetch(`/api/v1/conversations/${conversation.id}/stop`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({
        activeStreamId: conversation.activeResponseId,
        assistantMessage: last?.role === "assistant" ? last : undefined,
      }),
    });
    void stop();
  };

  return (
    <>
      <div
        className="h-full min-w-0 transition-[margin] duration-200"
        style={{
          marginRight: openDocument
            ? "clamp(36rem, 60vw, 64rem)"
            : undefined,
        }}
      >
        <ChatView
          title={showTitle ? title : undefined}
          header={header}
          messages={displayMessages}
          placeholder={placeholder}
          composerStart={composerStart ?? (agent ? <AgentChip agent={agent} /> : undefined)}
          composerFooter={composerFooter}
          onSubmit={(text) => {
            sessionStorage.removeItem(stoppedStorageKey(conversation.id));
            setResume(true);
            void sendMessage({ text });
          }}
          onStop={onStop}
          isStreaming={isStreaming}
          onOpenDocument={setOpenDocument}
          onFeedback={(messageId, rating, comment) =>
            scoreMessage(conversation.id, messageId, rating, comment).then(
              () => undefined,
            )
          }
        />
      </div>
      {openDocument ? (
        <ResourceViewer
          fileId={openDocument.fileId}
          mediaType={openDocument.mediaType}
          page={openDocument.page ?? undefined}
          bbox={openDocument.bbox ?? undefined}
          regions={openDocument.regions}
          filename={openDocument.filename}
          onClose={() => setOpenDocument(null)}
        />
      ) : null}
    </>
  );
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function toUIMessages(messages: ConversationMessage[]): UIMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    parts: message.parts.flatMap((part) => {
      if (part.type === "text") {
        return [{ type: "text" as const, text: part.text ?? "" }];
      }
      if (part.type === "reasoning") {
        return [
          {
            type: "reasoning" as const,
            text: part.text ?? "",
            state: part.state === "streaming" ? ("streaming" as const) : ("done" as const),
          },
        ];
      }
      if (part.type === "source-url") {
        return [
          {
            type: "source-url" as const,
            sourceId: String(part.sourceId ?? ""),
            url: String(part.url ?? ""),
            title: typeof part.title === "string" ? part.title : undefined,
            snippet: part.snippet,
            publishedDate: part.publishedDate,
          } as UIMessage["parts"][number],
        ];
      }
      if (part.type === "source-document") {
        return [
          {
            type: "source-document" as const,
            sourceId: String(part.sourceId ?? ""),
            mediaType: String(part.mediaType ?? "application/pdf"),
            title: String(part.title ?? part.filename ?? ""),
            fileId: String(part.fileId ?? ""),
            filename: String(part.filename ?? ""),
            page: typeof part.page === "number" ? part.page : null,
            anchor: String(part.anchor ?? ""),
            bbox: Array.isArray(part.bbox) ? part.bbox : null,
            regions: Array.isArray(part.regions) ? part.regions : undefined,
            collectionId: String(part.collectionId ?? ""),
            snippet: typeof part.snippet === "string" ? part.snippet : undefined,
            providerMetadata: part.providerMetadata,
          } as unknown as UIMessage["parts"][number],
        ];
      }
      if (part.type.startsWith("tool-") || part.type === "dynamic-tool") {
        const toolName = String(
          part.toolName ??
            (part.type.startsWith("tool-")
              ? part.type.slice("tool-".length)
              : "tool"),
        );
        const state =
          part.state === "output-available" ||
          part.state === "input-available" ||
          part.state === "input-streaming" ||
          part.state === "output-error"
            ? part.state
            : part.output != null
              ? "output-available"
              : "input-available";
        return [
          {
            type: part.type === "dynamic-tool" ? "dynamic-tool" : part.type,
            toolCallId: String(part.toolCallId ?? ""),
            toolName,
            state,
            input: part.input,
            output: part.output,
          } as UIMessage["parts"][number],
        ];
      }
      return [];
    }),
  }));
}

function textFromUIMessage(message: UIMessage): string {
  return textFromParts(
    message.parts.map((part) =>
      part.type === "text"
        ? { type: "text", text: part.text }
        : { type: part.type },
    ),
  );
}

function sourcesFromUIMessage(message: UIMessage): ChatMessage["sources"] {
  const sources: NonNullable<ChatMessage["sources"]> = [];
  for (const part of message.parts) {
    if (part.type === "source-url") {
      const extra = part as {
        sourceId: string;
        url: string;
        title?: string;
        snippet?: string;
        publishedDate?: string | null;
      };
      if (extra.sourceId && extra.url) {
        sources.push({
          type: "source-url" as const,
          sourceId: extra.sourceId,
          url: extra.url,
          title: extra.title,
          snippet: extra.snippet,
          publishedDate: extra.publishedDate,
        });
      }
      continue;
    }
    if (part.type === "source-document") {
      const extra = part as unknown as {
        sourceId: string;
        title?: string;
        mediaType?: string;
        fileId?: string;
        filename?: string;
        page?: number;
        anchor?: string;
        bbox?: number[];
        regions?: number[][];
        collectionId?: string;
        snippet?: string;
        providerMetadata?: {
          chatkb?: Record<string, unknown>;
        };
      };
      const metadata = extra.providerMetadata?.chatkb;
      const filename = extra.filename ?? extra.title ?? "";
      if (extra.sourceId && filename) {
        sources.push({
          type: "source-document" as const,
          sourceId: extra.sourceId,
          fileId: String(extra.fileId ?? metadata?.fileId ?? ""),
          filename,
          mediaType: String(extra.mediaType ?? "application/pdf"),
          page: optionalNumber(extra.page ?? metadata?.page),
          anchor: String(extra.anchor ?? metadata?.anchor ?? ""),
          bbox: optionalNumericArray(extra.bbox ?? metadata?.bbox),
          regions: numericRegions(extra.regions ?? metadata?.regions),
          collectionId: String(
            extra.collectionId ?? metadata?.collectionId ?? "",
          ),
          snippet:
            extra.snippet ??
            (typeof metadata?.snippet === "string"
              ? metadata.snippet
              : undefined),
        });
      }
    }
  }
  return sources;
}

function numericArray(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is number => typeof item === "number");
}

function optionalNumericArray(value: unknown): number[] | null {
  const values = numericArray(value);
  return values.length ? values : null;
}

function optionalNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numericRegions(value: unknown): number[][] | undefined {
  if (!Array.isArray(value)) return undefined;
  const regions = value
    .map(numericArray)
    .filter((region) => region.length === 4);
  return regions.length ? regions : undefined;
}

