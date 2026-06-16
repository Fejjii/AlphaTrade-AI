"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { PositionSizingResult } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

export function LossAcceptancePanel({
  sizing,
  proposalId,
  onAccepted,
}: {
  sizing: PositionSizingResult;
  proposalId?: string;
  onAccepted?: (accepted: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [blocked, setBlocked] = useState(false);

  async function confirm(accepted: boolean) {
    setBusy(true);
    setMessage(null);
    try {
      if (proposalId) {
        await api.proposals.lossAcceptance(proposalId, {
          planned_loss_amount: sizing.planned_loss_amount,
          accepted,
        });
      } else {
        const result = await api.risk.lossAcceptance({
          planned_loss_amount: sizing.planned_loss_amount,
          accepted,
        });
        if (!result.can_execute_paper) {
          setBlocked(true);
          setMessage(result.recommendation);
        }
      }
      onAccepted?.(accepted);
      if (accepted) {
        setMessage("Loss calmly accepted (paper gate only).");
        setBlocked(false);
      } else {
        setBlocked(true);
        setMessage("Reduce size or skip — paper execution remains blocked.");
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Loss acceptance failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Loss acceptance</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <p>Planned loss: {formatDecimal(sizing.planned_loss_amount)}</p>
        <p>Stop distance: {formatDecimal(sizing.stop_loss_distance)}</p>
        <p>Max acceptable loss: {formatDecimal(sizing.maximum_acceptable_loss)}</p>
        <p className="text-zinc-400">{sizing.worst_case_scenario}</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={busy} onClick={() => void confirm(true)}>
            Calmly accept planned loss
          </Button>
          <Button variant="outline" disabled={busy} onClick={() => void confirm(false)}>
            Not acceptable — reduce or skip
          </Button>
        </div>
        {message ? (
          <p className={blocked ? "text-amber-400" : "text-emerald-400"}>{message}</p>
        ) : null}
        {blocked ? (
          <p className="text-xs text-zinc-500">Paper execution blocked until loss is accepted.</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
