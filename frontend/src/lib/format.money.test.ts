import { expect, it } from "vitest";
import { formatMoney } from "./format";
it.each([["0E-8", "0.00"], ["0.0106", "0.0106"], ["82234.4", "82,234.40"], ["0.00493406", "0.00493406"], ["-0.00000001", "-0.00000001"], ["1000.125", "1,000.13"], [null, "—"], ["", "—"]])("formats monetary %s without losing meaningful precision", (input, output) => { expect(formatMoney(input)).toBe(output); });
