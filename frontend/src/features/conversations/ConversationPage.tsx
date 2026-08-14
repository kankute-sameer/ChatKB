import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { ChatView, ComposerStartDefault } from "@/components/ChatView";
import { getToken } from "@/lib/api";
import { segmentsFromParts } from "@/lib/activity";
import type { ChatMessage } from "@/mocks/data";
import { getAgent, type Agent } from "@/lib/agents";
import { AgentChip } from "@/features/agents/AgentChip";
import {
  getConversation,
  notifyConversationsChanged,
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
  showMic = true,
  composerStart,
  composerFooter,
  onSettled,
}: {
  conversation: ConversationDetail;
  pendingText?: string;
  placeholder?: string;
  header?: ReactNode;
  showTitle?: boolean;
  showMic?: boolean;
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
    <ChatView
      title={showTitle ? title : undefined}
      header={header}
      messages={displayMessages}
      placeholder={placeholder}
      showMic={showMic}
      composerStart={
        composerStart ??
        (agent ? <AgentChip agent={agent} /> : <ComposerStartDefault />)
      }
      composerFooter={composerFooter}
      onSubmit={(text) => {
        sessionStorage.removeItem(stoppedStorageKey(conversation.id));
        setResume(true);
        void sendMessage({ text });
      }}
      onStop={onStop}
      isStreaming={isStreaming}
    />
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
  return message.parts.flatMap((part) => {
    if (part.type !== "source-url") return [];
    const extra = part as {
      sourceId: string;
      url: string;
      title?: string;
      snippet?: string;
      publishedDate?: string | null;
    };
    if (!extra.sourceId || !extra.url) return [];
    return [
      {
        sourceId: extra.sourceId,
        url: extra.url,
        title: extra.title,
        snippet: extra.snippet,
        publishedDate: extra.publishedDate,
      },
    ];
  });
}

