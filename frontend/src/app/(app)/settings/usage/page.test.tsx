import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SettingsUsageRedirectPage from "./page";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

describe("Settings usage shim (FP2-129)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("redirects to the Billing & Usage composite without rendering a body", () => {
    const { container } = render(<SettingsUsageRedirectPage />);
    expect(container).toBeEmptyDOMElement();
    expect(replace).toHaveBeenCalledWith("/settings/billing#usage");
  });
});
