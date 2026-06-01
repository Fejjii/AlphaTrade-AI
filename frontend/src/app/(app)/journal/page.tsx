"use client";

import { useCallback, useState } from "react";

import { JournalEntryCard } from "@/components/JournalEntryCard";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function JournalPage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [rationale, setRationale] = useState("");
  const [lessons, setLessons] = useState("");
  const [emotions, setEmotions] = useState("");
  const [mistakes, setMistakes] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const loader = useCallback(() => api.journal.list({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  async function createEntry() {
    if (!rationale.trim()) return;
    setBusy(true);
    setMessage(null);
    try {
      await api.journal.create({
        symbol,
        timeframe: "1h",
        direction: "long",
        entry_rationale: rationale,
        lessons: lessons.trim() || undefined,
        emotions: emotions
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
        mistakes: mistakes
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
      });
      setRationale("");
      setLessons("");
      setEmotions("");
      setMistakes("");
      setMessage("Journal entry saved. Lessons sync to the knowledge base when enabled.");
      await reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save entry");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Journal</h1>
        <p className="text-sm text-zinc-400">
          Capture rationale, emotions, mistakes, and lessons. Entries can feed future RAG context.
        </p>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="journal-symbol">Symbol</Label>
            <Input
              id="journal-symbol"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="journal-rationale">Entry rationale</Label>
          <Textarea
            id="journal-rationale"
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="journal-lessons">Lessons learned</Label>
          <Textarea id="journal-lessons" value={lessons} onChange={(e) => setLessons(e.target.value)} />
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="journal-emotions">Emotion tags (comma-separated)</Label>
            <Input id="journal-emotions" value={emotions} onChange={(e) => setEmotions(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="journal-mistakes">Mistake tags (comma-separated)</Label>
            <Input id="journal-mistakes" value={mistakes} onChange={(e) => setMistakes(e.target.value)} />
          </div>
        </div>
        <Button disabled={busy || !rationale.trim()} onClick={() => void createEntry()}>
          {busy ? "Saving…" : "Create journal entry"}
        </Button>
        {message ? (
          <p className={`text-sm ${message.includes("saved") ? "text-emerald-300" : "text-red-300"}`}>
            {message}
          </p>
        ) : null}
      </div>

      {loading ? <LoadingState label="Loading journal entries…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      <div className="grid gap-4">
        {data?.items.length ? (
          data.items.map((entry) => (
            <div key={entry.id} className="space-y-2">
              <JournalEntryCard entry={entry} />
              <Button
                variant="destructive"
                size="sm"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api.journal.delete(entry.id);
                    await reload();
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Delete entry
              </Button>
            </div>
          ))
        ) : (
          <EmptyState
            title="No journal entries"
            description="Record trades and lessons to build your personal learning loop."
          />
        )}
      </div>
    </div>
  );
}
