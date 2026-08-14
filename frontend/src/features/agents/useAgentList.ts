import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  AGENTS_CHANGED,
  listAgents,
  type Agent,
} from "@/lib/agents";

export function useAgentList(): Agent[] {
  const location = useLocation();
  const [items, setItems] = useState<Agent[]>([]);

  const load = useCallback(() => {
    void listAgents()
      .then(setItems)
      .catch(() => {
        setItems([]);
      });
  }, []);

  useEffect(() => {
    load();
    window.addEventListener(AGENTS_CHANGED, load);
    return () => window.removeEventListener(AGENTS_CHANGED, load);
  }, [load, location.pathname]);

  return items;
}
