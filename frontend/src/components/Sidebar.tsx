import { useMemo, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  BookOpen,
  LogOut,
  MessageSquareText,
  PanelLeft,
  Plus,
  Search,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { FeedbackDialog } from "@/components/FeedbackDialog";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/features/auth/AuthProvider";
import { useAgentList } from "@/features/agents/useAgentList";
import { useConversationList } from "@/features/conversations/useConversationList";
import { appearanceClassName } from "@/design/tokens";
import { cn } from "@/lib/utils";

const primaryNav = [
  { to: "/agents", label: "Agents", icon: User },
  { to: "/kb", label: "Knowledge base", icon: BookOpen },
] as const;

/** Shared by every sidebar text row — one class, one look. */
const rowClass =
  "flex h-row items-center gap-3 rounded-full px-2 font-sans text-nav font-ui text-ink transition-colors duration-color ease-out hover:bg-gray-100";

const rowActiveClass = "bg-gray-100";

const labelClass = "min-w-0 truncate font-sans text-nav font-ui";

function RowLabel({ children }: { children: ReactNode }) {
  return <span className={labelClass}>{children}</span>;
}

function rowLinkClass(isActive: boolean, collapsed?: boolean) {
  return cn(
    rowClass,
    collapsed && "justify-center gap-0 px-0",
    isActive && rowActiveClass,
  );
}

export function Sidebar() {
  const { logout, username } = useAuth();
  const chats = useConversationList();
  const agents = useAgentList();
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const filteredChats = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return chats;
    return chats.filter((thread) =>
      (thread.title ?? "New chat").toLowerCase().includes(needle),
    );
  }, [query, chats]);

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-border bg-sidebar p-4 font-sans text-nav font-ui text-ink",
        collapsed
          ? "w-sidebar-collapsed min-w-sidebar-collapsed px-2"
          : "w-sidebar min-w-sidebar",
      )}
    >
      <div className="mb-2 flex h-row items-center justify-between">
        {collapsed ? null : (
          <span className="truncate pl-title font-serif text-brand font-ui text-ink">
            Work Agents
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="size-icon shrink-0"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={() => setCollapsed((value) => !value)}
        >
          <PanelLeft className="size-icon text-ink" />
        </Button>
      </div>

      <NavLink
        to="/"
        end
        className={cn(rowClass, collapsed && "justify-center gap-0 px-0")}
      >
        <Plus className="size-icon shrink-0" strokeWidth={1.75} />
        {collapsed ? null : <RowLabel>New chat</RowLabel>}
      </NavLink>

      <nav className="flex flex-col">
        {primaryNav.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) => rowLinkClass(isActive, collapsed)}
            >
              <Icon className="size-icon shrink-0" strokeWidth={1.75} />
              {collapsed ? null : <RowLabel>{item.label}</RowLabel>}
            </NavLink>
          );
        })}
        {username === "alice" ? (
          <NavLink
            to="/observability"
            className={({ isActive }) => rowLinkClass(isActive, collapsed)}
          >
            <Activity className="size-icon shrink-0" strokeWidth={1.75} />
            {collapsed ? null : <RowLabel>Observability</RowLabel>}
          </NavLink>
        ) : null}
      </nav>

      {collapsed ? null : (
        <>
          <div className="mt-4 flex flex-col">
            <p className="flex h-row items-center px-2 font-sans text-nav font-ui text-ink-muted">
              Recent agents
            </p>
            {agents.map((agent) => (
              <NavLink
                key={agent.id}
                to={`/agents/${agent.id}`}
                className={({ isActive }) => rowLinkClass(isActive)}
              >
                <span
                  className={cn(
                    "size-icon shrink-0 rounded-full",
                    appearanceClassName(agent.appearance.key),
                  )}
                />
                <RowLabel>{agent.name}</RowLabel>
              </NavLink>
            ))}
          </div>

          <div className="mt-4 flex min-h-0 flex-1 flex-col">
            <div className="flex h-row items-center justify-between">
              <p className="flex h-row flex-1 items-center px-2 font-sans text-nav font-ui text-ink-muted">
                Recent chats
              </p>
              <Button
                variant="ghost"
                size="icon"
                className="size-icon shrink-0"
                aria-label="Search chats"
                onClick={() => setSearchOpen((value) => !value)}
              >
                <Search className="size-icon text-ink-muted" />
              </Button>
            </div>
            {searchOpen ? (
              <div className="px-2 pb-1">
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search chats"
                  autoFocus
                  className="h-row font-sans text-nav font-ui"
                />
              </div>
            ) : null}
            <div className="min-h-0 flex-1 overflow-auto">
              {filteredChats.map((thread) => (
                <NavLink
                  key={thread.id}
                  to={`/c/${thread.id}`}
                  className={({ isActive }) => rowLinkClass(isActive)}
                >
                  <RowLabel>{thread.title ?? "New chat"}</RowLabel>
                </NavLink>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="mt-auto pt-2">
        <button
          type="button"
          className={cn(
            rowClass,
            "w-full text-left",
            collapsed && "justify-center gap-0 px-0",
          )}
          aria-label="Send feedback"
          title={collapsed ? "Feedback" : undefined}
          onClick={() => setFeedbackOpen(true)}
        >
          <MessageSquareText
            className="size-icon shrink-0"
            strokeWidth={1.75}
          />
          {collapsed ? null : <RowLabel>Feedback</RowLabel>}
        </button>
      </div>

      <div className="mt-2 border-t border-border pt-2">
        {collapsed ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-icon"
            aria-label="Sign out"
            onClick={logout}
          >
            <LogOut className="size-icon" />
          </Button>
        ) : (
          <div className={cn(rowClass, "justify-between")}>
            <RowLabel>
              <span className="text-ink-muted">{username}</span>
            </RowLabel>
            <Button
              variant="ghost"
              size="sm"
              className="h-auto px-2 font-sans text-nav font-ui text-ink"
              onClick={logout}
            >
              Sign out
            </Button>
          </div>
        )}
      </div>
      <FeedbackDialog open={feedbackOpen} onOpenChange={setFeedbackOpen} />
    </aside>
  );
}
