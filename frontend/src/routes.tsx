import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import { LoginPage } from "@/features/auth/LoginPage";
import { GuestOnly, RequireAuth } from "@/features/auth/guards";
import { ChatHomePage } from "@/features/chat/ChatHomePage";
import { AgentsGalleryPage } from "@/features/agents/AgentsGalleryPage";
import { AgentChatPage } from "@/features/agents/AgentChatPage";
import { AgentDetailPage } from "@/features/agents/AgentDetailPage";
import { ConversationPage } from "@/features/conversations/ConversationPage";
import { KnowledgeBaseListPage } from "@/features/kb/KnowledgeBaseListPage";
import { KnowledgeBaseDetailPage } from "@/features/kb/KnowledgeBaseDetailPage";

export const router = createBrowserRouter([
  {
    element: <GuestOnly />,
    children: [{ path: "/login", element: <LoginPage /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/", element: <ChatHomePage /> },
          { path: "/agents", element: <AgentsGalleryPage /> },
          { path: "/agents/:id", element: <AgentChatPage /> },
          { path: "/agents/:id/builder", element: <AgentDetailPage /> },
          { path: "/c/:id", element: <ConversationPage /> },
          { path: "/chat/:id", element: <Navigate to="/" replace /> },
          { path: "/kb", element: <KnowledgeBaseListPage /> },
          { path: "/kb/:id", element: <KnowledgeBaseDetailPage /> },
          { path: "*", element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
]);
