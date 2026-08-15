import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  COLLECTIONS_CHANGED,
  listCollections,
  type Collection,
} from "@/lib/kb";

export function useCollectionList(): Collection[] {
  const location = useLocation();
  const [items, setItems] = useState<Collection[]>([]);

  const load = useCallback(() => {
    void listCollections()
      .then(setItems)
      .catch(() => {
        setItems([]);
      });
  }, []);

  useEffect(() => {
    load();
    window.addEventListener(COLLECTIONS_CHANGED, load);
    return () => window.removeEventListener(COLLECTIONS_CHANGED, load);
  }, [load, location.pathname]);

  return items;
}
