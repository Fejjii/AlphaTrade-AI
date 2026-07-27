"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";

type KnowledgeStorePanelProps = {
  onStored?: () => void;
};

/** Manual ingest using the existing knowledge ingest API (trading_playbook). */
export function KnowledgeStorePanel({ onStored }: KnowledgeStorePanelProps) {
  const [title, setTitle] = useState("Playbook note");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ingest() {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.knowledge.ingest({
        title,
        text,
        source_type: "trading_playbook",
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
        <h2 id="knowledge-store-heading" className="text-lg font-semibold text-text-primary">
          Store knowledge manually
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Ingests plain text as source_type trading_playbook. Edit and delete are not available
          through the current API.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Ingest text document</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="knowledge-ingest-title">Title</Label>
            <Input
              id="knowledge-ingest-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              data-testid="knowledge-ingest-title"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="knowledge-ingest-text">Document text</Label>
            <Textarea
              id="knowledge-ingest-text"
              value={text}
              onChange={(event) => setText(event.target.value)}
              data-testid="knowledge-ingest-text"
            />
          </div>
          <Button
            disabled={busy || !text.trim()}
            onClick={() => void ingest()}
            data-testid="knowledge-ingest-submit"
          >
            {busy ? "Storing…" : "Store document"}
          </Button>
          {message ? (
            <p className="text-sm text-success" data-testid="knowledge-ingest-success">
              {message}
            </p>
          ) : null}
          {error ? (
            <p className="text-sm text-danger" role="alert" data-testid="knowledge-ingest-error">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}
