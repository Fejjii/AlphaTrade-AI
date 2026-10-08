import type { ManualDemoInput, ManualDemoInstrument } from "./api/manual-demo";

// Venue increments need exact decimal arithmetic; floating-point modulo can
// reject valid fractional contracts. Numbers are used only for display estimates.
const SCALE = BigInt(10) ** BigInt(18);
function decimal(value: string): bigint | null {
  if (!/^(?:\d{1,24})(?:\.\d{1,18})?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  const result = BigInt(whole) * SCALE + BigInt(fraction.padEnd(18, "0"));
  return result > BigInt(0) ? result : null;
}

export function validateManualDemoInput(
  input: ManualDemoInput,
  instrument: ManualDemoInstrument,
): string | null {
  const quantity = decimal(input.quantity);
  const stop = decimal(input.stop);
  const target = decimal(input.target);
  if (!quantity || !stop || !target) return "Exchange constraints: enter positive decimal contracts, stop and target.";
  const minimum = decimal(instrument.minimum_quantity);
  const maximum = decimal(instrument.maximum_quantity);
  const lot = decimal(instrument.lot_increment);
  const tick = decimal(instrument.tick_size);
  const price = decimal(instrument.reference_price);
  const multiplier = decimal(instrument.contract_multiplier);
  const minimumNotional = decimal(instrument.minimum_notional);
  if (!minimum || !maximum || !lot || !tick || !price || !multiplier || !minimumNotional) return "Exchange instrument metadata is unreadable. Refresh instrument limits.";
  if (quantity < minimum || quantity > maximum || quantity % lot !== BigInt(0)) return `Exchange constraints: use ${instrument.minimum_quantity}–${instrument.maximum_quantity} contracts in increments of ${instrument.lot_increment}. Quantity is contracts, not BTC.`;
  if (stop % tick !== BigInt(0) || target % tick !== BigInt(0)) return `Exchange constraints: stop and target must use the ${instrument.tick_size} USDT price increment.`;
  const lower = price * BigInt(999);
  const upper = price * BigInt(1001);
  if (input.side === "BUY" ? stop * BigInt(1000) >= lower || target * BigInt(1000) <= upper : stop * BigInt(1000) <= upper || target * BigInt(1000) >= lower) return "Manual demo geometry: long needs stop below and target above the entry range; short needs stop above and target below it. No minimum 1R applies.";
  if (quantity * multiplier * lower < minimumNotional * SCALE * SCALE * BigInt(1000)) return `Manual demo limit: entry notional must be at least ${instrument.minimum_notional} USDT.`;
  return null;
}
