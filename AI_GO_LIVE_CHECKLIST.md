# AI Go-Live Checklist

## Ready
- [x] RAG endpoint with citations and bounded inputs/outputs.
- [x] Policy drafting endpoint with deterministic fallback.
- [x] Optional Azure LLM mode behind feature flags.
- [x] Org-level AI controls page (limits, LLM toggle, rate limits).
- [x] AI usage event persistence (`ai_usage_events`).
- [x] AI usage export as CSV.
- [x] AI usage visible in System Logs (`log_type=ai`).
- [x] AI usage retention controls:
  - [x] CLI cleanup command (`prune-ai-usage-events`).
  - [x] In-app retention run from AI Controls page (dry-run supported).
- [x] Targeted regression tests for AI controls, RAG, and policy draft APIs.

## Pending (for full production go-live)
- [ ] Azure OpenAI production provisioning and deployments.
- [ ] Cost budgets/alerts and quota policy in Azure subscription.
- [ ] Secret management finalization (prod key rotation process).
- [ ] Production smoke test with real org data and audit sign-off.
- [ ] Scheduled retention execution (cron/task runner) if manual operation is insufficient.

## Recommended deployment order
1. Keep deterministic mode active in production first.
2. Enable Azure LLM for limited pilot org(s).
3. Monitor AI usage/cost and log quality.
4. Gradually expand access once budget + quality thresholds are stable.
