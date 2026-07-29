"use client";

/**
 * Keyboard-only bypass of the sidebar, top bar, and status strip (WCAG 2.4.1).
 *
 * `<main>` is not focusable by default, so the click handler moves focus
 * explicitly; the hash href keeps the link working without JavaScript.
 */
export function SkipLink({ targetId = "main" }: { targetId?: string }) {
  return (
    <a
      href={`#${targetId}`}
      data-testid="skip-link"
      className="sr-only rounded-control bg-accent px-4 py-3 text-sm font-semibold text-accent-foreground focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:outline-none focus:ring-2 focus:ring-focus"
      onClick={() => {
        const target = document.getElementById(targetId);
        if (!target) return;
        target.focus({ preventScroll: false });
      }}
    >
      Skip to main content
    </a>
  );
}
