"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import {
  formatKnowledgeTimestamp,
  formatSourceType,
  knowledgeCategory,
  resolveKnowledgeRelationships,
  type DeepLinkExclusionNotice,
} from "@/components/knowledge/knowledgeDisplay";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RagDocument } from "@/lib/api/types";

type KnowledgeDocumentCardProps = {
  document: RagDocument;
  highlighted?: boolean;
  deepLinkNotices?: DeepLinkExclusionNotice[];
  expanded?: boolean;
  onToggleExpand?: () => void;
  detailSlot?: ReactNode;
};

export function KnowledgeDocumentCard({
  document,
  highlighted = false,
  deepLinkNotices = [],
  expanded = false,
  onToggleExpand,
  detailSlot,
}: KnowledgeDocumentCardProps) {
  const category = knowledgeCategory(document);
  const relationships = resolveKnowledgeRelationships(document);
  const createdLabel = formatKnowledgeTimestamp(document.created_at);
  const updatedLabel = formatKnowledgeTimestamp(document.updated_at);

  return (
    <Card
      id={`knowledge-document-${document.id}`}
      data-testid={`knowledge-document-card-${document.id}`}
      className={
        highlighted
          ? "min-w-0 border-info-border ring-2 ring-focus"
          : "min-w-0 border-border-subtle"
      }
    >
      <CardHeader className="min-w-0 space-y-2 pb-2">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
          <CardTitle className="min-w-0 break-words text-base text-text-primary">
            {document.title}
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info" data-testid="knowledge-category-badge">
              {category.label}
            </Badge>
            <Badge variant="muted" data-testid="knowledge-source-type-badge">
              {formatSourceType(document.source_type)}
            </Badge>
          </div>
        </div>
        <p className="break-all text-xs text-text-muted" data-testid="knowledge-document-id">
          ID: {document.id}
        </p>
        {deepLinkNotices.map((notice) => (
          <p
            key={notice.kind}
            role="status"
            data-testid={notice.testId}
            className="break-words text-sm text-warning"
          >
            {notice.message}
          </p>
        ))}
      </CardHeader>
      <CardContent className="min-w-0 space-y-3 text-sm text-text-secondary">
        <div data-testid="knowledge-source-context" className="min-w-0 space-y-1">
          <p className="break-words">
            <span className="text-text-muted">Source type: </span>
            {formatSourceType(document.source_type)}
          </p>
          <p className="break-all">
            <span className="text-text-muted">Source URI: </span>
            {document.source_uri?.trim() ? document.source_uri : "unavailable"}
          </p>
          <p>
            <span className="text-text-muted">Version: </span>
            {document.version}
          </p>
          <p>
            <span className="text-text-muted">Created: </span>
            {createdLabel ?? "freshness unavailable"}
          </p>
          <p>
            <span className="text-text-muted">Updated: </span>
            {updatedLabel ?? "freshness unavailable"}
          </p>
        </div>

        <ul className="min-w-0 space-y-1" data-testid="knowledge-relationships">
          {relationships.length === 0 ? (
            <li
              className="text-text-muted"
              data-testid="knowledge-relationship-none"
            >
              No stored relationship identifiers on this document.
            </li>
          ) : (
            relationships.map((link) => (
              <li
                key={`${link.kind}-${link.id ?? "missing"}`}
                className="min-w-0 break-words"
                data-testid={`knowledge-relationship-${link.kind}`}
              >
                {link.href && link.id ? (
                  <Link href={link.href} className="break-all underline text-text-primary">
                    {link.label}: open
                  </Link>
                ) : (
                  <span
                    data-testid={`knowledge-relationship-unavailable-${link.kind}`}
                    className="text-text-muted"
                  >
                    {link.label}: {link.unavailableReason ?? "unavailable"}
                  </span>
                )}
              </li>
            ))
          )}
        </ul>

        {onToggleExpand ? (
          <button
            type="button"
            className="inline-flex h-10 items-center rounded-control border border-border bg-surface-1 px-4 text-sm font-medium text-text-primary hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            data-testid={`knowledge-expand-${document.id}`}
            aria-expanded={expanded}
            onClick={onToggleExpand}
          >
            {expanded ? "Hide detail" : "Show detail"}
          </button>
        ) : null}

        {expanded ? detailSlot : null}
      </CardContent>
    </Card>
  );
}
