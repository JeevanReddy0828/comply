// The control catalog is effectively static, so fetch it once per session and
// keep a control_id -> ControlDetail lookup in memory. Detail (description,
// evidence_requirements) is fetched lazily and cached on first use — that's the
// data the remediation/Add-Evidence UI needs.

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { ControlDetail, ControlSummary } from "../api/types";

interface CatalogState {
  summaries: Record<string, ControlSummary>;
  ready: boolean;
  /** Lazily load + cache full detail for one control. */
  getDetail: (controlId: string) => Promise<ControlDetail>;
}

const CatalogContext = createContext<CatalogState | null>(null);

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [summaries, setSummaries] = useState<Record<string, ControlSummary>>({});
  const [ready, setReady] = useState(false);
  const detailCache = useRef<Map<string, Promise<ControlDetail>>>(new Map());

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
        /* dashboard still works without the catalog map; names just fall back to ids */
      })
      .finally(() => active && setReady(true));
    return () => {
      active = false;
    };
  }, []);

  const getDetail = useCallback((controlId: string): Promise<ControlDetail> => {
    const cached = detailCache.current.get(controlId);
    if (cached) return cached;
    const p = api.getControl(controlId);
    detailCache.current.set(controlId, p);
    return p;
  }, []);

  return <CatalogContext value={{ summaries, ready, getDetail }}>{children}</CatalogContext>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCatalog(): CatalogState {
  const ctx = useContext(CatalogContext);
  if (!ctx) throw new Error("useCatalog must be used within CatalogProvider");
  return ctx;
}
