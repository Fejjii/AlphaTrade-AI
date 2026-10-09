# Workspace screenshots

Synthetic authenticated fixtures, captured in Chromium at desktop 1280×900 and
mobile 390×900. All balances, dates, trades, Agent prose and Saved receipts are
test data, not live provider or BloFin acceptance. Full-page mobile captures
temporarily expand the capture viewport so fixed navigation sits at the image
bottom; interaction/overflow/dialog checks use the original 390×900 viewport.

| View | Desktop | Mobile |
| --- | --- | --- |
| Dashboard | [1280](fixture-dashboard-1280.png) | [390](fixture-dashboard-390.png) |
| Pause dialog | [1280](fixture-pause-dialog-1280.png) | [390](fixture-pause-dialog-390.png) |
| Agent and receipt | [1280](fixture-agent-1280.png) | [390](fixture-agent-390.png) |
| Journal list | [1280](fixture-journal-list-1280.png) | [390](fixture-journal-list-390.png) |
| Exact Journal detail | [1280](fixture-journal-1280.png) | [390](fixture-journal-390.png) |
| Knowledge filters | [1280](fixture-knowledge-1280.png) | [390](fixture-knowledge-390.png) |
| Strategies | [1280](fixture-strategies-1280.png) | [390](fixture-strategies-390.png) |
| Settings | [1280](fixture-settings-1280.png) | [390](fixture-settings-390.png) |

Reproduce with `frontend/e2e/workspace-redesign.spec.ts`, using the commands and
limitations in [the implementation/presentation guide](../../alphatrade_workspace_redesign.md).
