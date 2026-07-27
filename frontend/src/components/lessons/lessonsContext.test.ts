import { describe, expect, it } from "vitest";

import {
  lessonsAllSourcesHref,
  lessonsCoachingFilterHref,
  parseLessonsQuery,
} from "@/components/lessons/lessonsContext";
import { resolveLessonRelationships } from "@/components/lessons/lessonDisplay";

describe("parseLessonsQuery", () => {
  it("parses candidate and coaching filter", () => {
    const params = new URLSearchParams("candidate=abc&source=coaching");
    expect(parseLessonsQuery(params)).toEqual({
      candidateId: "abc",
      sourceFilter: "coaching",
    });
  });
});

describe("lessons filter href helpers", () => {
  it("preserves candidate in all-sources and coaching filter links", () => {
    expect(lessonsAllSourcesHref("abc")).toBe("/lessons?candidate=abc");
    expect(lessonsCoachingFilterHref("abc")).toBe("/lessons?source=coaching&candidate=abc");
  });

  it("omits candidate param when not provided", () => {
    expect(lessonsAllSourcesHref()).toBe("/lessons");
    expect(lessonsCoachingFilterHref()).toBe("/lessons?source=coaching");
  });
});

describe("resolveLessonRelationships", () => {
  it("links journal only when related_journal_entry_id exists", () => {
    const links = resolveLessonRelationships({
      id: "l1",
      organization_id: "o",
      user_id: "u",
      source_type: "journal",
      related_journal_entry_id: "entry-1",
      lesson_text: "text",
      mistake_type: "early_exit",
      severity: "medium",
      status: "pending_review",
      created_at: "2026-07-20T10:00:00.000Z",
    });
    const journal = links.find((link) => link.kind === "journal");
    expect(journal?.href).toBe("/journal?entry=entry-1");
  });

  it("does not treat related_trade_id as journal link", () => {
    const links = resolveLessonRelationships({
      id: "l1",
      organization_id: "o",
      user_id: "u",
      source_type: "journal",
      related_trade_id: "trade-1",
      lesson_text: "text",
      mistake_type: "early_exit",
      severity: "medium",
      status: "pending_review",
      created_at: "2026-07-20T10:00:00.000Z",
    });
    const trade = links.find((link) => link.kind === "trade_reference");
    expect(trade?.href).toBeNull();
    expect(trade?.unavailableReason).toMatch(/not treated as a journal-entry link/i);
  });
});
