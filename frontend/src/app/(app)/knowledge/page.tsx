"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import { EmptyState, ErrorState } from "@/components/states";
import { api } from "@/lib/api";
import type { RagSearchResponse } from "@/lib/api/types";

export default function KnowledgePage() {
  const [title, setTitle] = useState("Playbook note");
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<RagSearchResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function ingest() {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result =       await api.knowledge.ingest({
        title,
        text,
        source_type: "trading_playbook",
      });
      setMessage(`Ingested ${result.chunk_count} chunks (${result.document_id})`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  async function runSearch() {
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setSearch(await api.knowledge.search({ query, top_k: 5 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Knowledge Base</h1>
        <p className="text-sm text-zinc-400">Ingest playbook text and search with citations.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ingest text document</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="text">Document text</Label>
            <Textarea id="text" value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <Button disabled={busy} onClick={() => void ingest()}>
            Ingest document
          </Button>
          {message ? <p className="text-sm text-emerald-300">{message}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Search knowledge base</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search query" />
          <Button disabled={busy} onClick={() => void runSearch()}>
            Search
          </Button>
        </CardContent>
      </Card>

      {error ? <ErrorState message={error} /> : null}

      {search ? (
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Results for “{search.query}”</h2>
          {search.chunks.length ? (
            search.chunks.map((chunk) => (
              <Card key={chunk.chunk_id}>
                <CardHeader>
                  <CardTitle className="text-sm">{chunk.title ?? chunk.document_id}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-zinc-300">
                  <p>{chunk.content}</p>
                  <p className="mt-2 text-zinc-500">Score: {chunk.score.toFixed(3)}</p>
                </CardContent>
              </Card>
            ))
          ) : (
            <EmptyState title="No chunks matched" />
          )}
          {search.citations.length ? (
            <Card>
              <CardHeader>
                <CardTitle>Citations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-zinc-400">
                {search.citations.map((citation) => (
                  <p key={citation.chunk_id}>{citation.snippet ?? citation.title}</p>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
