"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { PaperModeBanner } from "@/components/PaperModeBanner";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api, ApiError } from "@/lib/api";
import type { UserRiskSettings, UserRiskSettingsUpdate } from "@/lib/api/types";

type FormState = {
  daily_loss_limit: string;
  daily_target: string;
  max_trades_per_day: string;
  max_risk_per_trade_percent: string;
  default_account_balance: string;
  timezone: string;
  green_day_protection_enabled: boolean;
  one_loss_stop_enabled: boolean;
  overtrading_guard_enabled: boolean;
  notes: string;
};

function toFormState(settings: UserRiskSettings): FormState {
  return {
    daily_loss_limit: settings.daily_loss_limit ?? "",
    daily_target: settings.daily_target ?? "",
    max_trades_per_day: String(settings.max_trades_per_day),
    max_risk_per_trade_percent: settings.max_risk_per_trade_percent,
    default_account_balance: settings.default_account_balance,
    timezone: settings.timezone,
    green_day_protection_enabled: settings.green_day_protection_enabled,
    one_loss_stop_enabled: settings.one_loss_stop_enabled,
    overtrading_guard_enabled: settings.overtrading_guard_enabled,
    notes: settings.notes ?? "",
  };
}

function toPayload(form: FormState): UserRiskSettingsUpdate {
  return {
    daily_loss_limit: form.daily_loss_limit.trim() ? form.daily_loss_limit.trim() : null,
    daily_target: form.daily_target.trim() ? form.daily_target.trim() : null,
    max_trades_per_day: Number(form.max_trades_per_day),
    max_risk_per_trade_percent: form.max_risk_per_trade_percent.trim(),
    default_account_balance: form.default_account_balance.trim(),
    timezone: form.timezone.trim() || "UTC",
    green_day_protection_enabled: form.green_day_protection_enabled,
    one_loss_stop_enabled: form.one_loss_stop_enabled,
    overtrading_guard_enabled: form.overtrading_guard_enabled,
    notes: form.notes.trim() ? form.notes.trim() : null,
  };
}

export default function RiskSettingsPage() {
  const loader = useCallback(() => api.risk.settings(), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);
  const [form, setForm] = useState<FormState | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    if (data) setForm(toFormState(data));
  }, [data]);

  if (loading) return <LoadingState label="Loading risk settings…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!form) return <ErrorState message="Risk settings unavailable." onRetry={() => void reload()} />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    setSaveError(null);
    setSavedMessage(null);
    try {
      const updated = await api.risk.updateSettings(toPayload(form));
      setForm(toFormState(updated));
      setSavedMessage("Risk settings saved.");
    } catch (err) {
      setSaveError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Unable to save risk settings.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    setSaving(true);
    setSaveError(null);
    setSavedMessage(null);
    try {
      const updated = await api.risk.resetSettings();
      setForm(toFormState(updated));
      setSavedMessage("Risk settings reset to defaults.");
    } catch (err) {
      setSaveError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Unable to reset risk settings.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Risk Settings</h1>
        <p className="text-sm text-zinc-400">
          Configure paper discipline limits and protective signals. These guide simulated trading only —
          not live exchange execution.
        </p>
      </div>

      <PaperModeBanner />

      <Card data-testid="risk-settings-form-card">
        <CardHeader>
          <CardTitle>Paper discipline limits</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="text-zinc-300">Daily loss limit</span>
                <Input
                  data-testid="risk-daily-loss-limit"
                  value={form.daily_loss_limit}
                  onChange={(e) => setForm({ ...form, daily_loss_limit: e.target.value })}
                  placeholder="e.g. 50"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-zinc-300">Daily profit target</span>
                <Input
                  data-testid="risk-daily-target"
                  value={form.daily_target}
                  onChange={(e) => setForm({ ...form, daily_target: e.target.value })}
                  placeholder="e.g. 100"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-zinc-300">Max trades per day</span>
                <Input
                  data-testid="risk-max-trades"
                  type="number"
                  min={1}
                  value={form.max_trades_per_day}
                  onChange={(e) => setForm({ ...form, max_trades_per_day: e.target.value })}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-zinc-300">Max risk per trade (%)</span>
                <Input
                  data-testid="risk-max-risk-percent"
                  value={form.max_risk_per_trade_percent}
                  onChange={(e) => setForm({ ...form, max_risk_per_trade_percent: e.target.value })}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-zinc-300">Default account balance</span>
                <Input
                  data-testid="risk-default-balance"
                  value={form.default_account_balance}
                  onChange={(e) => setForm({ ...form, default_account_balance: e.target.value })}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-zinc-300">Timezone</span>
                <Input
                  data-testid="risk-timezone"
                  value={form.timezone}
                  onChange={(e) => setForm({ ...form, timezone: e.target.value })}
                />
              </label>
            </div>

            <div className="space-y-2 text-sm text-zinc-300">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  data-testid="risk-green-day"
                  checked={form.green_day_protection_enabled}
                  onChange={(e) =>
                    setForm({ ...form, green_day_protection_enabled: e.target.checked })
                  }
                />
                Green day protection
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  data-testid="risk-one-loss-stop"
                  checked={form.one_loss_stop_enabled}
                  onChange={(e) => setForm({ ...form, one_loss_stop_enabled: e.target.checked })}
                />
                One loss stop
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  data-testid="risk-overtrading-guard"
                  checked={form.overtrading_guard_enabled}
                  onChange={(e) =>
                    setForm({ ...form, overtrading_guard_enabled: e.target.checked })
                  }
                />
                Overtrading guard
              </label>
            </div>

            <label className="block space-y-1 text-sm">
              <span className="text-zinc-300">Notes (optional)</span>
              <Input
                data-testid="risk-notes"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </label>

            {data?.using_defaults ? (
              <p className="text-xs text-amber-500/80" data-testid="risk-using-defaults">
                Using system defaults until you save personalized settings.
              </p>
            ) : null}

            {saveError ? (
              <p className="text-sm text-red-400" data-testid="risk-settings-error">
                {saveError}
              </p>
            ) : null}
            {savedMessage ? (
              <p className="text-sm text-emerald-400" data-testid="risk-settings-saved">
                {savedMessage}
              </p>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={saving} data-testid="risk-settings-save">
                Save settings
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={saving}
                onClick={() => void handleReset()}
                data-testid="risk-settings-reset"
              >
                Reset defaults
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <p className="text-xs text-zinc-500">
        Real trading remains disabled. Risk settings affect paper discipline snapshots, dashboard guidance,
        and agent explanations — never broker execution.
      </p>
    </div>
  );
}
