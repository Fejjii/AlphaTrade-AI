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
    window.addEventListener("alphatrade:status-changed", onReconnect);
    window.addEventListener("focus", onReconnect);
    window.addEventListener("online", onReconnect);
    return () => {
      window.removeEventListener("alphatrade:status-changed", onReconnect);
      window.removeEventListener("focus", onReconnect);
      window.removeEventListener("online", onReconnect);
    };
  }, [reload]);

  return { data, loading, error, reload };
}
