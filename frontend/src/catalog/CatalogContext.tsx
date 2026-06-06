// The control catalog is effectively static, so fetch it once per session and
// keep a control_id -> ControlSummary lookup in memory. Today that's used for
// human-readable control names; full control detail can be added when there's
// a control-detail experience to back it.

import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { ControlSummary } from "../api/types";

interface CatalogState {
  summaries: Record<string, ControlSummary>;
}

const CatalogContext = createContext<CatalogState | null>(null);

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [summaries, setSummaries] = useState<Record<string, ControlSummary>>({});

  useEffect(() => {
    let active = true;
    api
      .listControls()
      .then((controls) => {
        if (!active) return;
        const map: Record<string, ControlSummary> = {};
        for (const c of controls) map[c.control_id] = c;
        setSummaries(map);
      })
      .catch(() => {
        /* names just fall back to control ids if the catalog can't be loaded */
      });
    return () => {
      active = false;
    };
  }, []);

  return <CatalogContext value={{ summaries }}>{children}</CatalogContext>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCatalog(): CatalogState {
  const ctx = useContext(CatalogContext);
  if (!ctx) throw new Error("useCatalog must be used within CatalogProvider");
  return ctx;
}
