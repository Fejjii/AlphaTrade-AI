"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { PaperAccountStatus } from "@/lib/api/types";

export function PaperAccountSetup() {
  const [status, setStatus] = useState<PaperAccountStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);

  useEffect(() => {
    let active = true;
    void api.execution.paperAccountStatus().then(
      (result) => {
        if (active) setStatus(result);
      },
      (failure: unknown) => {
        if (active) {
          setError(
            failure instanceof Error
              ? failure.message
              : "Paper account status is unavailable.",
          );
        }
      },
    );
    return () => {
      active = false;
    };
  }, []);

  async function setup() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await api.execution.registerPaperAccount();
      setStatus({ account: result.account, can_register: true });
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Paper account setup failed.",
      );
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <p className="text-sm text-text-muted">Paper execution account</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-text-muted">
          Register a PAPER/NET identity for governed paper execution. Execution
          still requires its existing approvals and safety checks.
        </p>
        {error && (
          <p role="alert" className="text-sm text-red-400">
            {error}
          </p>
        )}
        {status?.account ? (
          <div role="status" className="space-y-1 text-sm">
            <p>Paper account registered · PAPER / NET</p>
            <details>
              <summary className="min-h-11 cursor-pointer">
                Account reference
              </summary>
              <p>
                Account UUID:{" "}
                <code className="break-all select-all">
                  {status.account.id}
                </code>
              </p>
            </details>
          </div>
        ) : status ? (
          status.can_register ? (
            <Button disabled={busy} onClick={() => void setup()}>
              {busy ? "Setting up…" : "Set up paper account"}
            </Button>
          ) : (
            <p className="text-sm text-text-muted">
              Only an organization owner can set up a paper account.
            </p>
          )
        ) : (
          !error && (
            <p role="status" className="text-sm">
              Checking paper account…
            </p>
          )
        )}
      </CardContent>
    </Card>
  );
}
