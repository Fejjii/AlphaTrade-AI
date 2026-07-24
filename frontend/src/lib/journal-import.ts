/**
 * Journal bulk import helpers (AT-033): CSV parsing, column mapping, and row
 * normalization. Pure functions — no I/O — so parsing and mapping stay
 * unit-testable. The backend remains the validation authority; client-side
 * checks only flag obviously malformed rows before the dry-run.
 */

import type { JournalImportRowInput } from "@/lib/api/types";

export const MAX_IMPORT_ROWS = 500;

export type ImportFieldKey =
  | "symbol"
  | "timeframe"
  | "direction"
  | "status"
  | "exchange"
  | "strategy_label"
  | "entry_price"
  | "entry_time"
  | "exit_price"
  | "exit_time"
  | "exit_reason"
  | "size"
  | "leverage"
  | "fees"
  | "funding"
  | "slippage"
  | "gross_pnl"
  | "net_pnl"
  | "result"
  | "notes"
  | "tags"
  | "external_ref";

export interface ImportFieldSpec {
  key: ImportFieldKey;
  label: string;
  required: boolean;
  kind: "text" | "number" | "datetime" | "direction" | "tags";
}

export const IMPORT_FIELDS: readonly ImportFieldSpec[] = [
  { key: "symbol", label: "Symbol", required: true, kind: "text" },
  { key: "direction", label: "Direction (long/short)", required: true, kind: "direction" },
  { key: "timeframe", label: "Timeframe", required: false, kind: "text" },
  { key: "entry_price", label: "Entry price", required: false, kind: "number" },
  { key: "entry_time", label: "Entry time", required: false, kind: "datetime" },
  { key: "exit_price", label: "Exit price", required: false, kind: "number" },
  { key: "exit_time", label: "Exit time", required: false, kind: "datetime" },
  { key: "size", label: "Size", required: false, kind: "number" },
  { key: "leverage", label: "Leverage", required: false, kind: "number" },
  { key: "fees", label: "Fees", required: false, kind: "number" },
  { key: "funding", label: "Funding", required: false, kind: "number" },
  { key: "slippage", label: "Slippage", required: false, kind: "number" },
  { key: "gross_pnl", label: "Gross PnL", required: false, kind: "number" },
  { key: "net_pnl", label: "Net PnL", required: false, kind: "number" },
  { key: "result", label: "Result (win/loss/breakeven)", required: false, kind: "text" },
  { key: "status", label: "Status", required: false, kind: "text" },
  { key: "exchange", label: "Exchange", required: false, kind: "text" },
  { key: "strategy_label", label: "Strategy label", required: false, kind: "text" },
  { key: "exit_reason", label: "Exit reason", required: false, kind: "text" },
  { key: "notes", label: "Notes", required: false, kind: "text" },
  { key: "tags", label: "Tags", required: false, kind: "tags" },
  { key: "external_ref", label: "External ref (dedup id)", required: false, kind: "text" },
] as const;

/** Header aliases for auto-detection; keys are normalized header names. */
const HEADER_ALIASES: Record<string, ImportFieldKey> = {
  symbol: "symbol",
  pair: "symbol",
  market: "symbol",
  instrument: "symbol",
  ticker: "symbol",
  timeframe: "timeframe",
  tf: "timeframe",
  interval: "timeframe",
  direction: "direction",
  side: "direction",
  position: "direction",
  status: "status",
  exchange: "exchange",
  venue: "exchange",
  strategy: "strategy_label",
  strategylabel: "strategy_label",
  setup: "strategy_label",
  entryprice: "entry_price",
  openprice: "entry_price",
  avgentryprice: "entry_price",
  entrytime: "entry_time",
  opentime: "entry_time",
  entrydate: "entry_time",
  opened: "entry_time",
  openedat: "entry_time",
  exitprice: "exit_price",
  closeprice: "exit_price",
  avgexitprice: "exit_price",
  exittime: "exit_time",
  closetime: "exit_time",
  exitdate: "exit_time",
  closed: "exit_time",
  closedat: "exit_time",
  exitreason: "exit_reason",
  closereason: "exit_reason",
  size: "size",
  qty: "size",
  quantity: "size",
  amount: "size",
  contracts: "size",
  leverage: "leverage",
  fees: "fees",
  fee: "fees",
  commission: "fees",
  funding: "funding",
  fundingfee: "funding",
  slippage: "slippage",
  grosspnl: "gross_pnl",
  netpnl: "net_pnl",
  pnl: "net_pnl",
  profit: "net_pnl",
  realizedpnl: "net_pnl",
  result: "result",
  outcome: "result",
  notes: "notes",
  note: "notes",
  comment: "notes",
  tags: "tags",
  labels: "tags",
  externalref: "external_ref",
  externalid: "external_ref",
  tradeid: "external_ref",
  orderid: "external_ref",
  id: "external_ref",
  ref: "external_ref",
};

export interface ParsedCsv {
  headers: string[];
  rows: string[][];
}

/** Detect the most plausible delimiter from the header line. */
function detectDelimiter(headerLine: string): string {
  const candidates = [",", ";", "\t"];
  let best = ",";
  let bestCount = 0;
  for (const candidate of candidates) {
    const count = headerLine.split(candidate).length - 1;
    if (count > bestCount) {
      best = candidate;
      bestCount = count;
    }
  }
  return best;
}

/**
 * Tolerant CSV parser: quoted fields (including embedded delimiters/newlines
 * and doubled quotes), CRLF, delimiter auto-detection, empty lines skipped.
 */
export function parseCsv(text: string): ParsedCsv {
  const normalized = text.replace(/^\uFEFF/, "");
  const firstLineEnd = normalized.indexOf("\n");
  const headerLine = firstLineEnd === -1 ? normalized : normalized.slice(0, firstLineEnd);
  const delimiter = detectDelimiter(headerLine.replace(/\r$/, ""));

  const records: string[][] = [];
  let field = "";
  let record: string[] = [];
  let inQuotes = false;

  const pushField = () => {
    record.push(field.trim());
    field = "";
  };
  const pushRecord = () => {
    pushField();
    if (record.some((value) => value !== "")) {
      records.push(record);
    }
    record = [];
  };

  for (let i = 0; i < normalized.length; i += 1) {
    const char = normalized[i];
    if (inQuotes) {
      if (char === '"') {
        if (normalized[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      inQuotes = true;
    } else if (char === delimiter) {
      pushField();
    } else if (char === "\n") {
      pushRecord();
    } else if (char !== "\r") {
      field += char;
    }
  }
  if (field !== "" || record.length > 0) {
    pushRecord();
  }

  const [headers = [], ...rows] = records;
  return { headers, rows };
}

export type ColumnMapping = Partial<Record<ImportFieldKey, number>>;

/** Best-effort column auto-detection from normalized header names. */
export function autoDetectMapping(headers: string[]): ColumnMapping {
  const mapping: ColumnMapping = {};
  headers.forEach((header, index) => {
    const normalized = header.toLowerCase().replace(/[^a-z0-9]/g, "");
    const field = HEADER_ALIASES[normalized];
    if (field !== undefined && mapping[field] === undefined) {
      mapping[field] = index;
    }
  });
  return mapping;
}

export interface RowIssue {
  index: number;
  messages: string[];
}

export interface BuiltRows {
  rows: JournalImportRowInput[];
  issues: RowIssue[];
}

function normalizeDirection(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  if (["long", "buy", "b"].includes(normalized)) return "long";
  if (["short", "sell", "s"].includes(normalized)) return "short";
  return null;
}

function normalizeNumber(value: string): string | null {
  const cleaned = value.replace(/[,\s]/g, "").replace(/[$€£]/g, "");
  if (cleaned === "") return null;
  return Number.isFinite(Number(cleaned)) ? cleaned : null;
}

function normalizeDatetime(value: string): string | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  // Numeric epochs: seconds or milliseconds.
  if (/^\d{10}(\d{3})?$/.test(trimmed)) {
    const ms = trimmed.length === 13 ? Number(trimmed) : Number(trimmed) * 1000;
    const fromEpoch = new Date(ms);
    return Number.isNaN(fromEpoch.getTime()) ? null : fromEpoch.toISOString();
  }
  const parsed = new Date(trimmed);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function normalizeTags(value: string): string[] {
  return value
    .split(/[;|,]/)
    .map((tag) => tag.trim())
    .filter((tag) => tag !== "");
}

/**
 * Build backend import rows from parsed CSV data and a column mapping.
 * Collects per-row client-side issues; issue rows are still submitted so the
 * backend dry-run report stays the single source of truth.
 */
export function buildRows(
  parsed: ParsedCsv,
  mapping: ColumnMapping,
  options: { defaultTimeframe: string },
): BuiltRows {
  const rows: JournalImportRowInput[] = [];
  const issues: RowIssue[] = [];

  parsed.rows.forEach((csvRow, index) => {
    const messages: string[] = [];
    const cell = (key: ImportFieldKey): string => {
      const column = mapping[key];
      if (column === undefined || column >= csvRow.length) return "";
      return csvRow[column] ?? "";
    };

    const symbol = cell("symbol").trim().toUpperCase();
    if (symbol === "") {
      messages.push("symbol is empty");
    }

    const rawDirection = cell("direction");
    const direction = normalizeDirection(rawDirection);
    if (direction === null) {
      messages.push(
        rawDirection.trim() === ""
          ? "direction is empty"
          : `direction "${rawDirection}" is not long/short`,
      );
    }

    const timeframe = cell("timeframe").trim().toLowerCase() || options.defaultTimeframe;

    const draft: Record<string, unknown> = {
      symbol,
      timeframe,
      direction: direction ?? rawDirection.trim().toLowerCase(),
    };

    for (const spec of IMPORT_FIELDS) {
      if (["symbol", "timeframe", "direction"].includes(spec.key)) continue;
      const raw = cell(spec.key).trim();
      if (raw === "") continue;
      if (spec.kind === "number") {
        const value = normalizeNumber(raw);
        if (value === null) {
          messages.push(`${spec.key} "${raw}" is not a number`);
        } else {
          draft[spec.key] = value;
        }
      } else if (spec.kind === "datetime") {
        const value = normalizeDatetime(raw);
        if (value === null) {
          messages.push(`${spec.key} "${raw}" is not a valid date/time`);
        } else {
          draft[spec.key] = value;
        }
      } else if (spec.kind === "tags") {
        draft.tags = normalizeTags(raw);
      } else {
        draft[spec.key] = raw;
      }
    }
    if (typeof draft.status === "string") {
      draft.status = draft.status.trim().toLowerCase();
    }
    if (typeof draft.result === "string") {
      draft.result = draft.result.trim().toLowerCase();
    }

    rows.push(draft as unknown as JournalImportRowInput);
    if (messages.length > 0) {
      issues.push({ index, messages });
    }
  });

  return { rows, issues };
}
