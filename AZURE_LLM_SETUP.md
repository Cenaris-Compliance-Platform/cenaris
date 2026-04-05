# Azure OpenAI setup for Cenaris (low cost)

## 1) Create the Azure OpenAI resource
1. Sign in to Azure Portal.
2. Create a new resource: Azure OpenAI.
3. Choose the same region as your app if possible (lower latency).
4. After creation, open the resource and go to Keys and Endpoint.

You will need:
- Endpoint URL
- API key

## 2) Deploy the models (mini + writer)
In Azure OpenAI Studio (inside the resource):
1. Go to Deployments.
2. Create two deployments:
   - Mini model (recommended for document review): GPT-4o-mini
   - Writer model (for long policy generation): GPT-4o

Suggested deployment names:
- gpt-4o-mini
- gpt-4o

## 3) Configure the app environment
Add these environment variables in your server environment (.env or hosting config):

- AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
- AZURE_OPENAI_API_KEY=YOUR_KEY
- AZURE_OPENAI_API_VERSION=2024-10-21
- AZURE_OPENAI_CHAT_DEPLOYMENT_MINI=gpt-4o-mini
- AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER=gpt-4o
- AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini
- AZURE_OPENAI_TIMEOUT_SECONDS=60
- AZURE_OPENAI_SUMMARY_MAX_OUTPUT_TOKENS=450
- AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS=1400

Notes:
- The app prefers AZURE_OPENAI_CHAT_DEPLOYMENT_MINI for AI Review summaries.
- Policy drafting uses AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER by default.

## 4) Cost control (recommended)
### A) Use GPT-4o-mini for audit/review
- AI Review uses GPT-4o-mini (cheap).
- Only policy writing uses GPT-4o (expensive).

### B) Keep output short
- AZURE_OPENAI_SUMMARY_MAX_OUTPUT_TOKENS keeps summaries short.
- AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS keeps policy drafts controlled.

### C) Keep RAG small
- AI Review uses limited top-k citations and short snippets.

### D) Use Azure budgets and alerts
Azure does not provide a hard dollar cap for paid subscriptions, but you can enforce a strong safety net with budgets and quota limits.

Steps to set a budget:
1. Azure Portal -> Cost Management + Billing.
2. Budgets -> Add.
3. Set a monthly budget (for example, $10).
4. Add alerts at 50%, 80%, 100%.

Optional quota limits:
1. In the Azure OpenAI resource, open Quotas.
2. Set lower TPM (tokens per minute) and RPM (requests per minute).
3. This caps usage so you cannot spike costs.

## 5) Which model we are using now
- AI Review summaries: GPT-4o-mini (AZURE_OPENAI_CHAT_DEPLOYMENT_MINI).
- Policy writing: GPT-4o (AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER).

## 6) Recommended defaults for low cost
- GPT-4o-mini for all analysis and checklist review.
- GPT-4o only for long policy generation.
- Keep summary outputs short (<= 450 tokens).
- Use a monthly budget alert.

If you want, I can also add a "hard off" switch in the app that disables all LLM calls when a budget threshold is reached (based on AIUsageEvent totals).
