import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { ChatView } from "@/components/ChatView";
import { getToken } from "@/lib/api";
import type { ChatMessage } from "@/mocks/data";
import {
  getConversation,
  notifyConversationsChanged,
  reasoningFromParts,
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

  return <ConversationChat conversation={conversation} />;
}

function ConversationChat({
  conversation,
}: {
  conversation: ConversationDetail;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const pendingText = (location.state as LocationState | null)?.pendingText;
  const sentPending = useRef(false);
  const [resume, setResume] = useState(
    () => sessionStorage.getItem(stoppedStorageKey(conversation.id)) == null,
  );

  const [title, setTitle] = useState(conversation.title ?? "New chat");

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

  const displayMessages: ChatMessage[] = messages.map((message, index) => {
    const content = textFromUIMessage(message);
    const thought = reasoningFromUIMessage(message);
    const isLast = index === messages.length - 1;
    return {
      id: message.id,
      threadId: conversation.id,
      role: message.role === "user" ? "user" : "assistant",
      content,
      thought: thought || undefined,
      thoughtStreaming:
        isStreaming &&
        isLast &&
        message.role !== "user" &&
        Boolean(thought) &&
        !content.trim(),
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
      title={title}
      messages={displayMessages}
      placeholder="Ask anything..."
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

function reasoningFromUIMessage(message: UIMessage): string {
  return reasoningFromParts(
    message.parts.map((part) =>
      part.type === "reasoning"
        ? { type: "reasoning", text: part.text }
        : { type: part.type },
    ),
  );
}
