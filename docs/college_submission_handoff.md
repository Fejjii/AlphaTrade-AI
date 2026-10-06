# College submission: source snapshot and review gates

Prepared October 6, 2026 from main
`e75e8bf411918094bd50eaf3d633d459efd40b40`, including PR215.
Destination: <https://github.com/TuringCollegeSubmissions/sofejji-AFA.BAI.1.8>.

## Access blocker and destination preservation

Destination inspection failed: authenticated Git returned **403 / write access not
granted** even for `ls-remote`; the GitHub connector returned **404**. This does not
prove the repository is absent. No destination file, branch, setting or workflow
has been changed, and reviewer content has not been inspected.

The authenticated GitHub actor/App needs access to this exact organization repository:
**Contents: read/write** to inspect it and publish a new review branch, and
**Pull requests: write** to open the submission PR. Authorize the App installation
for the repository and organization SSO if applicable. Do not rotate production
credentials or copy credentials into code to resolve this access problem.

## Accurate presentation status

| Claim | Evidence and limit |
| --- | --- |
| Agent continuity, readable trade answers and Knowledge import entry | Implemented in merged PR215. Supervisor reports deployed; no independent live conversational/import acceptance performed by this task. Preview and explicit save grant no strategy/risk/Journal authority. |
| Nested internal-paper workflow | Source exists; earlier supervisor reports one genuine market event through risk, fill, Journal and Telegram. One event establishes neither profitability nor complete product acceptance. |
| Minimum planned reward/risk | [PR216](https://github.com/Fejjii/AlphaTrade-AI/pull/216) is a prospective review branch, not deployed. The old canonical path lacked this floor; reported BTC short is approximately 0.65R. |
| Linked setup/assessment context | PR216 adds scoped compiled setup, immutable decision and integrity-checked assessment summaries. A full rule snapshot may still be absent; inaccessible stores are not proof of absent records. Live synthesis acceptance remains pending. |
| Journal targets | New projection producer is implemented. Existing empty rows require the [audited scoped repair](journal_plan_target_repair.md), independently verified ownership and supervising apply. No live repair was run here. |
| Five-market BloFin demo | PR212–214 implementation is merged. Instrument/strategy configuration and actual protected venue fill, exit and same-account repeat acceptance remain unverified. Real trading is disabled; SFP has no execution authority. |
| CI / evaluation | Focused development evidence is scoped to its tested commit. Complete backend acceptance requires one consolidated exact-SHA `full_backend=true` CI dispatch plus evaluation/browser smoke. This task does not dispatch it. |
| Future vision | Broader Agent capabilities, undocumented outcome/PnL semantics and profitability remain planned or unproven, not features established by screenshots or mocks. |

Use existing [architecture](architecture.md), [Agent](agent_workflow.md),
[retrieval](rag_system.md), [testing](evaluation.md), [pitch](interview_pitch.md)
and [demo](demo_script.md) guides. Their stated historical bases and results remain
preserved; this dated addendum supplies changes since their inspection. Do not
rewrite old results as new acceptance or claim a review branch is deployed.

## Safe one-way synchronization procedure

This is prepared for the supervising follow-up once destination access is granted;
**synchronization is blocked until inspection**. No reverse synchronization or
force push is permitted.

1. Fetch the approved consolidated AlphaTrade source and record its exact commit.
   Include PR216 only after reviewed integration; otherwise label it pending and
   use the merged baseline. Keep the source working tree/configuration untouched.
2. Clone the destination into a new directory. Record its default branch and exact
   HEAD. Read its README, reviewer feedback/rubric, existing source layout, branch
   rules, `.github/workflows`, deployment configuration and linked deployment hooks.
   Inventory tracked files before copying. Check that a review-branch push/PR will
   not trigger another deployment; do not change repository settings to bypass it.
3. Make a fresh destination review branch from that recorded HEAD. Preserve every
   reviewer-owned file, comment/rubric and existing workflow/deployment file. Prepare
   an explicit source-path → destination-path manifest based on the inspected layout.
   Collisions require review; do not replace the destination README wholesale.
   If a project directory is appropriate, use an unused directory rather than
   deleting or resetting reviewer content. No `rsync --delete`, mirror push or
   replacement of destination Git history is allowed.
4. Export **tracked files at the pinned source commit**, never a working-tree copy.
   Include application source, tests, dependency manifests/locks, local Compose,
   required synthetic evaluation data and the existing relevant documentation.
   Exclude `.git`, `.github/workflows`, `render.yaml`, agent handoffs, environment
   files except reviewed placeholder templates, private keys/credentials, production
   data, local databases/logs, build/cache/dependency directories and unscreened
   captures. Inspect the export for secrets/private content before copying anything.
   Templates and local commands must retain paper/mock mode with real trading off.
5. Apply only the reviewed manifest, then inspect `git diff --name-status`, every
   deletion/overwrite and the full diff. Verify reviewer files and existing automation
   are byte-identical to destination HEAD. Record source SHA, destination base SHA,
   manifest, export hashes and intentional omissions in the submission PR. Inspect
   the final tracked file list again for secrets and deployment automation.
6. Run focused checks for changed code/doc links only, push the new branch normally,
   and open a destination PR. Do not merge it, enable Actions/deployments, move tags,
   change remotes in the production checkout or force push. The reviewer decides
   acceptance. Preserve exact source and destination provenance for later one-way
   updates; each subsequent sync starts with a new inventory and reviewed diff.

The inability to inspect destination contents is the remaining permission gate,
not a reason to assume reviewer files or deployment hooks are safe to overwrite.
