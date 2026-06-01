"use client";

import { OctagonAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAppContext } from "@/contexts/AppContext";

export function KillSwitchButton({ compact = false }: { compact?: boolean }) {
  const { killSwitchActive, toggleKillSwitch } = useAppContext();

  return (
    <Button
      variant={killSwitchActive ? "destructive" : "outline"}
      size={compact ? "sm" : "default"}
      onClick={toggleKillSwitch}
      aria-pressed={killSwitchActive}
    >
      <OctagonAlert className="h-4 w-4" />
      {killSwitchActive ? "Kill switch ON" : "Kill switch"}
    </Button>
  );
}
