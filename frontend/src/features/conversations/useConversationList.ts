import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  CONVERSATIONS_CHANGED,
  listConversations,
  type ConversationSummary,
} from "@/lib/conversations";

export function useConversationList(): ConversationSummary[] {
  const location = useLocation();
  const [items, setItems] = useState<ConversationSummary[]>([]);

  const load = useCallback(() => {
    void listConversations()
      .then(setItems)
      .catch(() => {
        setItems([]);
      });
  }, []);

  useEffect(() => {
    load();
    window.addEventListener(CONVERSATIONS_CHANGED, load);
    return () => window.removeEventListener(CONVERSATIONS_CHANGED, load);
  }, [load, location.pathname]);

  return items;
}
