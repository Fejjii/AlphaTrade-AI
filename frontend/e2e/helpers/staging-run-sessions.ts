import { APIRequestContext, expect } from "@playwright/test";

export const STAGING_API_URL =
  process.env.PLAYWRIGHT_API_URL ?? "https://alphatrade-api-staging.onrender.com";

const CREATE_DRAFT = "CREATE_PAPER_VALIDATION_DRAFT";
const QUEUE_CANDIDATE = "QUEUE_PAPER_VALIDATION_CANDIDATE";
const CREATE_PLAN = "CREATE_PAPER_VALIDATION_RUN_PLAN";
const START_RUN = "START_PAPER_VALIDATION_RUN";

const READY_PREP = {
  prep_status: "ready_for_validation",
  thesis: "Staging smoke thesis.",
  entry_criteria: "Entry criteria for staging smoke.",
  invalidation_criteria: "Invalidation criteria for staging smoke.",
  risk_notes: "Conservative staging smoke prep.",
  checklist: {
    trend_checked: true,
    support_resistance_checked: true,
    volume_checked: true,
    risk_reward_checked: true,
    invalidation_checked: true,
    higher_timeframe_checked: true,
    news_or_funding_checked: true,
  },
};

const PLAN_PAYLOAD = {
  confirm: CREATE_PLAN,
  validation_window: "intraday",
  observation_timeframe: "1h",
  max_duration_minutes: 240,
  planned_entry_rule: "Wait for confirmation around trigger level.",
  planned_invalidation_rule: "Invalid if price closes beyond invalidation level.",
  planned_success_criteria: "Price moves toward target without invalidation.",
  planned_failure_criteria: "Invalidation hit or thesis no longer valid.",
};

function authHeaders(accessToken: string) {
  return { Authorization: `Bearer ${accessToken}` };
}

export async function loginBootstrapOwner(
  request: APIRequestContext,
): Promise<{ accessToken: string }> {
  const email =
    process.env.STAGING_BOOTSTRAP_EMAIL ?? "seed-bootstrap-1782212606@example.com";
  const password = process.env.STAGING_BOOTSTRAP_PASSWORD ?? "";
  expect(password, "STAGING_BOOTSTRAP_PASSWORD required for run session staging smoke").toBeTruthy();

  const login = await request.post(`${STAGING_API_URL}/auth/login`, {
    data: { email, password },
  });
  expect(login.ok()).toBeTruthy();
  const auth = await login.json();
  return { accessToken: auth.tokens.access_token as string };
}

export async function buildPlannedPlanFromAlert(
  request: APIRequestContext,
  accessToken: string,
  alertId: string,
): Promise<string> {
  const headers = authHeaders(accessToken);

  const review = await request.get(`${STAGING_API_URL}/alerts/setup-review?limit=50`, {
    headers,
  });
  expect(review.ok()).toBeTruthy();
  const items = ((await review.json()).items ?? []) as Array<{
    alert_id: string;
    review_status?: string;
  }>;
  const alert = items.find((item) => item.alert_id === alertId);
  if (alert && !["watching", "important"].includes(alert.review_status ?? "")) {
    const patched = await request.patch(`${STAGING_API_URL}/alerts/setup-review/${alertId}`, {
      headers,
      data: { review_status: "important" },
    });
    expect(patched.ok()).toBeTruthy();
  }

  const draft = await request.post(`${STAGING_API_URL}/alerts/setup-review/${alertId}/draft`, {
    headers,
    data: {
      confirm: CREATE_DRAFT,
      risk_mode: "conservative",
      notes: "Run session staging smoke",
    },
  });
  expect(draft.ok()).toBeTruthy();
  const draftId = (await draft.json()).draft.draft_id as string;

  const prep = await request.patch(`${STAGING_API_URL}/paper-validation/drafts/${draftId}/prep`, {
    headers,
    data: READY_PREP,
  });
  expect(prep.ok()).toBeTruthy();

  const queued = await request.post(
    `${STAGING_API_URL}/paper-validation/drafts/${draftId}/queue`,
    {
      headers,
      data: { confirm: QUEUE_CANDIDATE },
    },
  );
  expect(queued.ok()).toBeTruthy();
  const candidateId = (await queued.json()).candidate.candidate_id as string;

  const reviewing = await request.patch(
    `${STAGING_API_URL}/paper-validation/candidates/${candidateId}`,
    {
      headers,
      data: { candidate_status: "reviewing" },
    },
  );
  expect(reviewing.ok()).toBeTruthy();

  const plan = await request.post(
    `${STAGING_API_URL}/paper-validation/candidates/${candidateId}/plan`,
    {
      headers,
      data: PLAN_PAYLOAD,
    },
  );
  expect(plan.ok()).toBeTruthy();
  return (await plan.json()).plan.plan_id as string;
}

export async function findOrCreateSecondPlannedPlan(
  request: APIRequestContext,
  accessToken: string,
  excludePlanId?: string,
): Promise<string> {
  const headers = authHeaders(accessToken);
  const plans = await request.get(`${STAGING_API_URL}/paper-validation/run-plans?limit=50`, {
    headers,
  });
  expect(plans.ok()).toBeTruthy();
  const planned = ((await plans.json()).items ?? []).find(
    (item: { plan_id: string; plan_status: string }) =>
      item.plan_status === "planned" && item.plan_id !== excludePlanId,
  );
  if (planned) {
    return planned.plan_id as string;
  }

  const review = await request.get(`${STAGING_API_URL}/alerts/setup-review?limit=50`, { headers });
  expect(review.ok()).toBeTruthy();
  const alerts = ((await review.json()).items ?? []) as Array<{ alert_id: string }>;
  expect(alerts.length).toBeGreaterThan(1);
  return buildPlannedPlanFromAlert(request, accessToken, alerts[1].alert_id);
}

export async function assertNonPlannedStartBlocked(
  request: APIRequestContext,
  accessToken: string,
  planId: string,
): Promise<void> {
  const headers = authHeaders(accessToken);
  const revised = await request.patch(`${STAGING_API_URL}/paper-validation/run-plans/${planId}`, {
    headers,
    data: { plan_status: "needs_revision" },
  });
  expect(revised.ok()).toBeTruthy();

  const blocked = await request.post(`${STAGING_API_URL}/paper-validation/run-plans/${planId}/start`, {
    headers,
    data: { confirm: START_RUN },
  });
  expect(blocked.status()).toBe(422);
}

export { START_RUN };
