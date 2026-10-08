import { test, expect } from "@playwright/test";

test.use({
  launchOptions: {
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {}),
    args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"],
  },
});
test.skip(({ browserName }) => browserName !== "chromium", "Chromium policy diagnostic.");

// A real Chromium engine and synthetic audio device isolate application policy.
// This is not proof of the affected Mac's device or speech recognition service.
test("Next app permits same-origin microphone capture and retains frame restrictions", async ({ page }) => {
  const response = await page.goto("/login");
  expect(response?.headers()["permissions-policy"]).toBe("camera=(), microphone=(self), geolocation=()");
  expect(response?.headers()["x-frame-options"]).toBe("DENY");
  expect(response?.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
  const evidence = await page.evaluate(async () => {
    const policy = (document as Document & { featurePolicy?: { allowsFeature(name: string): boolean } }).featurePolicy;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    const tracks = stream.getTracks();
    tracks.forEach((track) => track.stop());
    return { policyAllowsCapture: policy?.allowsFeature("microphone"), tracks: tracks.length, stopped: tracks.every((track) => track.readyState === "ended") };
  });
  expect(evidence).toEqual({ policyAllowsCapture: true, tracks: 1, stopped: true });
});

test("previous microphone denial header causes NotAllowedError despite an allowed synthetic device", async ({ page }) => {
  await page.route("**/microphone-policy-control", (route) => route.fulfill({
    status: 200, contentType: "text/html", body: "<html><body>Policy control</body></html>",
    headers: { "Permissions-Policy": "camera=(), microphone=(), geolocation=()" },
  }));
  await page.goto("/microphone-policy-control");
  const error = await page.evaluate(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      stream.getTracks().forEach((track) => track.stop());
      return "unexpected_capture";
    } catch (failure) {
      return failure instanceof DOMException ? failure.name : "unknown";
    }
  });
  expect(error).toBe("NotAllowedError");
});
