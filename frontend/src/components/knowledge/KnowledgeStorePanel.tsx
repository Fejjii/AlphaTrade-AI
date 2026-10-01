"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";

type KnowledgeStorePanelProps = {
  onStored?: () => void;
  initialSourceType?: "risk_policy" | "trading_playbook" | "general_note";
};

/** Plain-text creation through canonical ingestion; reviewed producers stay in their own flows. */
export function KnowledgeStorePanel({
  onStored,
  initialSourceType = "trading_playbook",
}: KnowledgeStorePanelProps) {
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<string>(initialSourceType);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ingest() {
    if (busy || !title.trim() || !text.trim()) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.knowledge.ingest({
        title: title.trim(),
        text: text.trim(),
        source_type: sourceType,
      });
      setMessage(
        `Stored document ${result.document_id} (${result.chunk_count} chunks${
          result.duplicate ? ", duplicate content" : ""
        }).`,
      );
      setText("");
      onStored?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="knowledge-store-heading"
      data-testid="knowledge-store-panel"
      className="space-y-3"
    >
      <div>
        <h2
          id="knowledge-store-heading"
          className="text-lg font-semibold text-text-primary"
        >
          Add a trading note
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Saved to your existing knowledge library. Existing documents cannot be
          edited here.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Trading note</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="knowledge-ingest-category">Category</Label>
            <Select
              id="knowledge-ingest-category"
              value={sourceType}
              disabled={busy}
              onChange={(event) => setSourceType(event.target.value)}
            >
              <option value="risk_policy">Trading Rules</option>
              <option value="trading_playbook">Playbook</option>
              <option value="general_note">Market Observations</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="knowledge-ingest-title">Title</Label>
            <Input
              id="knowledge-ingest-title"
              value={title}
              disabled={busy}
              onChange={(event) => setTitle(event.target.value)}
              data-testid="knowledge-ingest-title"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="knowledge-ingest-text">Document text</Label>
            <Textarea
              id="knowledge-ingest-text"
              value={text}
              disabled={busy}
              onChange={(event) => setText(event.target.value)}
              data-testid="knowledge-ingest-text"
            />
          </div>
          <Button
            disabled={busy || !title.trim() || !text.trim()}
            onClick={() => void ingest()}
            data-testid="knowledge-ingest-submit"
          >
            {busy ? "Saving…" : "Save note"}
          </Button>
          {message ? (
            <p
              role="status"
              className="break-words text-sm text-success"
              data-testid="knowledge-ingest-success"
            >
              {message}
            </p>
          ) : null}
          {error ? (
            <p
              className="text-sm text-danger"
              role="alert"
              data-testid="knowledge-ingest-error"
            >
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}
