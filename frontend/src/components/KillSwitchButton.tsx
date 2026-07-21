"use client";

import { OctagonAlert } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useAppContext } from "@/contexts/AppContext";

export function KillSwitchButton({ compact = false }: { compact?: boolean }) {
  const {
    killSwitchActive,
    killSwitchBusy,
    killSwitchError,
    setKillSwitchActive,
  } = useAppContext();
  const [localError, setLocalError] = useState<string | null>(null);

  async function handleClick() {
    setLocalError(null);
    const nextActive = !killSwitchActive;
    const actionLabel = nextActive ? "ACTIVATE" : "DEACTIVATE";
    const confirmed = window.confirm(
      `${actionLabel} organization kill switch?\n\n` +
        "This is a server-side control. When active, new paper execution is blocked " +
        "for the organization. Read-only portfolio views remain available.",
    );
    if (!confirmed) return;

    const reason = window.prompt(
      `Enter a reason for ${actionLabel.toLowerCase()} (required, min 3 characters):`,
      nextActive ? "Emergency halt" : "Resume paper trading",
    );
    if (reason == null) return;
    if (reason.trim().length < 3) {
      setLocalError("A reason of at least 3 characters is required.");
      return;
    }

    try {
      await setKillSwitchActive(nextActive, reason.trim());
    } catch {
      setLocalError(killSwitchError ?? "Kill switch update failed (owner role required).");
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant={killSwitchActive ? "destructive" : "outline"}
        size={compact ? "sm" : "default"}
        onClick={() => void handleClick()}
        disabled={killSwitchBusy}
        aria-pressed={killSwitchActive}
        title="Organization kill switch (owner only to change)"
      >
        <OctagonAlert className="h-4 w-4" />
        {killSwitchBusy
          ? "Updating…"
          : killSwitchActive
            ? "Kill switch ON"
            : "Kill switch"}
      </Button>
      {(localError || killSwitchError) && (
        <span className="max-w-[16rem] text-right text-xs text-red-400">
          {localError ?? killSwitchError}
        </span>
      )}
    </div>
  );
}
