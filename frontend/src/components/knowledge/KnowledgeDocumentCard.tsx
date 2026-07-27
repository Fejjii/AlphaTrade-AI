"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import {
  formatKnowledgeTimestamp,
  formatSourceType,
  knowledgeCategory,
  resolveKnowledgeRelationships,
} from "@/components/knowledge/knowledgeDisplay";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RagDocument } from "@/lib/api/types";

type KnowledgeDocumentCardProps = {
  document: RagDocument;
  highlighted?: boolean;
  deepLinkNotice?: boolean;
  filterMismatchNotice?: boolean;
  expanded?: boolean;
  onToggleExpand?: () => void;
  detailSlot?: ReactNode;
};

export function KnowledgeDocumentCard({
  document,
  highlighted = false,
  deepLinkNotice = false,
  filterMismatchNotice = false,
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
          ? "border-info-border ring-2 ring-focus"
          : "border-border-subtle"
      }
    >
      <CardHeader className="space-y-2 pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-base text-text-primary">{document.title}</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info" data-testid="knowledge-category-badge">
              {category.label}
            </Badge>
            <Badge variant="muted" data-testid="knowledge-source-type-badge">
              {formatSourceType(document.source_type)}
            </Badge>
          </div>
        </div>
        {deepLinkNotice ? (
          <p
            role="status"
            data-testid="knowledge-deeplink-notice"
            className="text-sm text-warning"
          >
            This document was opened from a direct link and was not present in the active filtered
            list page.
          </p>
        ) : null}
        {filterMismatchNotice ? (
          <p
            role="status"
            data-testid="knowledge-filter-mismatch-notice"
            className="text-sm text-warning"
          >
            This document does not match the active source filter, but remains visible because it
            was requested directly.
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-text-secondary">
        <div data-testid="knowledge-source-context" className="space-y-1">
          <p>
            <span className="text-text-muted">Source type: </span>
            {formatSourceType(document.source_type)}
          </p>
          <p>
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

        <ul className="space-y-1" data-testid="knowledge-relationships">
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
                data-testid={`knowledge-relationship-${link.kind}`}
              >
                {link.href && link.id ? (
                  <Link href={link.href} className="underline text-text-primary">
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
