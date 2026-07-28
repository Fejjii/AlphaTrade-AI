import type { ValidationDimension } from "./filterValidation";

export const VALIDATION_DIMENSION_LABELS: Record<ValidationDimension, string> = {
  condition: "Condition",
  timeframe: "Timeframe",
  symbol: "Symbol",
  direction: "Direction",
  confidence_bucket: "Confidence bucket",
};

/** Column header for setup_key values in setup-ranking responses. */
export function validationDimensionIdentityLabel(dimension: ValidationDimension): string {
  return VALIDATION_DIMENSION_LABELS[dimension];
}

export function validationRankingTitle(dimension: ValidationDimension): string {
  return `Validation ranking by ${VALIDATION_DIMENSION_LABELS[dimension]}`;
}

export function validationRankingCaption(dimension: ValidationDimension): string {
  return `Learning-analytics setup ranking by ${VALIDATION_DIMENSION_LABELS[dimension].toLowerCase()}`;
}

export function validationRankingSampleGateLabel(minSample: number): string {
  return `≥ ${minSample}`;
}
