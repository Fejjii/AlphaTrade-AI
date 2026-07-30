"use client";

import { useEffect, useId, useRef, useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import type { Position } from "@/lib/api/types";
import { formatMonetary, formatPrice, humanizeToken } from "@/lib/format";
import { formatDate } from "@/lib/utils";

/**
 * Validate a user-entered paper exit price.
 *
 * Returns the trimmed plain-decimal string when valid, otherwise `null`.
 * Only positive plain decimals are accepted (no signs, exponents, or symbols)
 * because the value is submitted verbatim as the recorded exit price.
 */
export function parseExitPrice(raw: string): string | null {
  const trimmed = raw.trim();
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return null;
  if (Number(trimmed) <= 0) return null;
  return trimmed;
}

type CloseStep = "idle" | "price" | "confirm";

export function PositionCard({
  position,
  onClosePaper,
}: {
  position: Position;
  /** Performs the paper close; must reject on API failure so the card can surface it. */
  onClosePaper?: (id: string, exitPrice: string) => Promise<void>;
}) {
  const fieldId = useId();
  const [step, setStep] = useState<CloseStep>("idle");
  const [exitPriceInput, setExitPriceInput] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  // Synchronous guard: state updates are async, so a rapid double-click could
  // otherwise submit the close twice before React re-renders the disabled button.
  const closingRef = useRef(false);
  const closePanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (step === "idle") return;
    // Keep the close flow above the fixed mobile bottom nav / home indicator.
    // jsdom does not implement scrollIntoView — guard before calling (CI/unit).
    const node = closePanelRef.current;
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  }, [step]);

  function startClose() {
    setSubmitError(null);
    setValidationError(null);
    setStep("price");
  }

  function cancelClose() {
    setStep("idle");
    setExitPriceInput("");
    setValidationError(null);
    setSubmitError(null);
  }

  function reviewClose() {
    const parsed = parseExitPrice(exitPriceInput);
    if (parsed === null) {
      setValidationError("Enter the exit price as a positive number, for example 50123.45.");
      return;
    }
    setExitPriceInput(parsed);
    setValidationError(null);
    setSubmitError(null);
    setStep("confirm");
  }

  async function confirmClose() {
    if (!onClosePaper || closingRef.current) return;
    const exitPrice = parseExitPrice(exitPriceInput);
    if (exitPrice === null) {
      setValidationError("Enter the exit price as a positive number, for example 50123.45.");
      setStep("price");
      return;
    }
    closingRef.current = true;
    setClosing(true);
    setSubmitError(null);
    try {
      await onClosePaper(position.id, exitPrice);
      setStep("idle");
      setExitPriceInput("");
    } catch (err) {
      const detail = err instanceof Error && err.message ? err.message : "Request failed";
      setSubmitError(`Close failed: ${detail}. The position remains open.`);
    } finally {
      closingRef.current = false;
      setClosing(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            {position.symbol} · {position.direction.toUpperCase()}
          </CardTitle>
          <StatusBadge label={position.status} tone={position.status === "open" ? "ok" : "muted"} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <div className="grid gap-1 sm:grid-cols-2">
          <span>Entry: {formatPrice(position.entry_price)}</span>
          <span>Size: {formatPrice(position.size)}</span>
          <span>Unrealized PnL: {formatMonetary(position.unrealized_pnl)}</span>
          <span>Opened: {formatDate(position.opened_at)}</span>
        </div>
        {Object.keys(position.risk_state).length > 0 ? (
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
            <p className="mb-2 text-xs uppercase tracking-wide text-zinc-500">Risk state</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(position.risk_state).map(([key, value]) => (
                <StatusBadge
                  key={key}
                  label={`${humanizeToken(key)}: ${String(value)}`}
                  tone="info"
                />
              ))}
            </div>
          </div>
        ) : null}
        {position.status === "open" && onClosePaper ? (
          step === "idle" ? (
            <Button variant="warning" onClick={startClose} data-testid="close-paper-start">
              Close paper position
            </Button>
          ) : (
            <div
              ref={closePanelRef}
              className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 scroll-mt-4 scroll-mb-[calc(5.5rem+env(safe-area-inset-bottom,0px))]"
              data-testid="close-paper-panel"
            >
              <p className="text-xs uppercase tracking-wide text-zinc-500">Close paper position</p>
              <p className="text-xs text-zinc-400">
                Current entry price: {formatPrice(position.entry_price)}. The exit price you
                enter is recorded exactly as typed — no price is assumed for you.
              </p>
              {step === "price" ? (
                <div className="space-y-2">
                  <Label htmlFor={fieldId}>Exit price</Label>
                  <Input
                    id={fieldId}
                    data-testid="close-paper-exit-price"
                    inputMode="decimal"
                    autoComplete="off"
                    placeholder="e.g. 50123.45"
                    value={exitPriceInput}
                    onChange={(event) => setExitPriceInput(event.target.value)}
                    aria-invalid={validationError ? true : undefined}
                    aria-describedby={validationError ? `${fieldId}-error` : undefined}
                  />
                  <FieldError id={`${fieldId}-error`} message={validationError} />
                  <div className="flex flex-wrap gap-2">
                    <Button variant="warning" onClick={reviewClose} data-testid="close-paper-review">
                      Review close
                    </Button>
                    <Button variant="ghost" onClick={cancelClose} data-testid="close-paper-cancel">
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="font-medium text-text-primary">Confirm paper close</p>
                  <dl
                    className="grid gap-1 text-sm text-zinc-300 sm:grid-cols-2"
                    data-testid="close-paper-confirmation"
                  >
                    <div>
                      <dt className="inline text-zinc-500">Symbol: </dt>
                      <dd className="inline">{position.symbol}</dd>
                    </div>
                    <div>
                      <dt className="inline text-zinc-500">Side: </dt>
                      <dd className="inline">{position.direction.toUpperCase()}</dd>
                    </div>
                    <div>
                      <dt className="inline text-zinc-500">Size: </dt>
                      <dd className="inline">{formatPrice(position.size)}</dd>
                    </div>
                    <div>
                      <dt className="inline text-zinc-500">Exit price: </dt>
                      <dd className="inline">{exitPriceInput}</dd>
                    </div>
                  </dl>
                  {submitError ? (
                    <p role="alert" data-testid="close-paper-error" className="text-caption text-danger">
                      {submitError}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="warning"
                      disabled={closing}
                      onClick={() => void confirmClose()}
                      data-testid="close-paper-confirm"
                    >
                      {closing ? "Closing…" : "Confirm paper close"}
                    </Button>
                    <Button
                      variant="ghost"
                      disabled={closing}
                      onClick={() => setStep("price")}
                      data-testid="close-paper-back"
                    >
                      Back
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )
        ) : null}
      </CardContent>
    </Card>
  );
}
