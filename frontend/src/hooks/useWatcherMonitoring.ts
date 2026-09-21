"use client";

import { useCallback, useEffect } from "react";

import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export function useWatcherMonitoring() {
  const loader = useCallback(() => api.marketWatcher.monitoring(), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  useEffect(() => {
    const onReconnect = () => {
      void reload();
    };
    window.addEventListener("focus", onReconnect);
    window.addEventListener("online", onReconnect);
    return () => {
      window.removeEventListener("focus", onReconnect);
      window.removeEventListener("online", onReconnect);
    };
  }, [reload]);

  return { data, loading, error, reload };
}
