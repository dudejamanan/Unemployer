# LinkedIn company-page publishing

## Current activation: Buffer

Company-page publishing is now **enabled through Buffer**, which supplies the LinkedIn integration. Your own LinkedIn Community Management approval is not required for this route. The API key stays in local `.env` as `BUFFER_API_KEY`; never commit or share it. The connected target was verified as the Unemployer company page, not a personal profile: https://www.linkedin.com/company/143986491.

A real Learntricks Edutech opportunity was published and Buffer returned `sent` status: https://www.linkedin.com/feed/update/urn:li:share:7515513578183938048. The adapter uses `shareNow`, automatic scheduling, and `needsApproval: false`; it does not wait for Buffer's usual posting slots.

Configuration in `config/shorts.yaml` selects `linkedin.provider: buffer` and stores the non-secret Buffer organization/channel IDs. `BUFFER_ORGANIZATION_ID` and `BUFFER_CHANNEL_ID` can override those IDs. `python -m shorts.linkedin check` verifies the connection; `status`, `preview`, `run`, and `resume` apply to the Buffer outbox too. Buffer account reconnection is handled in its dashboard, not `linkedin auth` (which belongs to the direct API route).

The independent publisher still reads the same video-ready opportunities, preserves stipend/deadline priorities, skips unpaid/expired/stale/rejected records, and records attempts separately from YouTube. Requests accepted by Buffer are marked `accepted`, not published. Only `sent` status is marked `posted`. Failed Buffer deliveries are held as `delivery_failed` for inspection; ambiguous create requests are reconciled by exact channel/content or saved Buffer post ID. A bounded scan of the latest 100 records never proves a missing post did not exist, so it never blindly recreates one.

For the Free plan, local rolling API budgets reserve at most 80 requests per 24 hours and 2,600 per 30 days, leaving room beneath Buffer's documented 100/3,000 limits for account setup and other usage. Connection checks cache for one hour. Buffer may apply other posting limits; local budgets and the default ten-post daily cap cannot override them. Requests from external clients using the same key are not included in the local ledger. A long-pending delivery can consume polling budget and postpone new posts; YouTube continues independently.

If the Buffer key is revoked, replace it privately in `.env` and restart the worker. Reconnect disconnected/paused/locked channels through Buffer. After fixing an explicitly rejected request, use `python -m shorts.linkedin resume`; uncertain and failed-delivery states are deliberately held. Database backups include the outbox and request-budget ledger. OAuth and API secrets remain separate private files.

Buffer references: https://developers.buffer.com/guides/posts-and-scheduling.html and https://developers.buffer.com/guides/api-limits.html.

## Optional direct LinkedIn API route

The instructions below apply only if you later obtain Community Management access and switch `linkedin.provider` away from `buffer`. Direct LinkedIn OAuth has not been live-verified.

## One-time setup

1. Create the Unemployer LinkedIn company page and become its administrator. The app must be associated with the correct page.
2. Create an app in https://www.linkedin.com/developers/apps and apply for **Community Management API** access. Basic personal-profile sharing access is insufficient for organization posts. LinkedIn decides approval and tier limits; the software cannot grant these.
3. Configure the exact OAuth redirect URL `http://localhost:8766/callback` in the app. Enable `w_organization_social` and `r_organization_social` as permitted by your approved product. Write access posts; read access supports uncertain-upload reconciliation.
4. Put the following values in the local `.env`, which must never be committed:

```dotenv
LINKEDIN_CLIENT_ID=your-app-client-id
LINKEDIN_CLIENT_SECRET=your-app-client-secret
LINKEDIN_ORGANIZATION_URN=urn:li:organization:YOUR_NUMERIC_PAGE_ID
LINKEDIN_API_VERSION=202609
LINKEDIN_TOKEN_FILE=secrets/linkedin_token.json
```

Use the company's numeric organization ID, not its vanity name. Supply credentials privately in the local file, not chat.

5. Run `python -m shorts.linkedin auth`. Sign in as a page administrator and authorize the app. The local callback validates a random OAuth state and times out after five minutes. Tokens are saved under ignored `secrets/`; the numeric author is bound to that local token record. The API still determines whether the signed-in member may publish for that page.
6. Run `python -m shorts.linkedin check` to verify company-page read access. Preview a current opening with `python -m shorts.linkedin preview <opportunity-id>`. Inspect its source facts and application URL. Write access is verified by the first successful live publish.
7. Set `linkedin.enabled: true` in `config/shorts.yaml`. Set an appropriate `daily_limit` for your approved tier. Run `python -m shorts.linkedin run` for a live initial cycle, inspect `python -m shorts.linkedin status`, and confirm the result on your actual page.
8. Restart the installed worker to load the integration: `Stop-ScheduledTask -TaskName UnemployerWorker`, then `Start-ScheduledTask -TaskName UnemployerWorker`.

## Parallel pipeline

The single scheduled worker owns the process lock and starts an independent LinkedIn publishing thread with its own SQLite connection. It checks every 15 seconds. Once an opportunity's YouTube video reaches ready/uploading/posted state, LinkedIn can publish its factual text post independently of YouTube's success. It uses company, role, location, disclosed stipend, known deadline, a general application tip, source URL, and relevant hashtags. Sponsored source designations add an explicit disclosure. This integration creates text posts with links; it does not upload the Shorts MP4 to LinkedIn.

Both platforms use the same opportunity selection and stipend/deadline priorities. LinkedIn excludes closed, expired, rejected, stale (>24 hours since source check), and configured unpaid opportunities. Existing active YouTube-ready/posted opportunities may be backfilled when LinkedIn is first enabled, subject to its daily cap. Rendering failures mean no ready video and therefore no LinkedIn dispatch for that item.

Exact simultaneous publication cannot be guaranteed across two external APIs. LinkedIn normally dispatches within one polling interval of the video becoming ready; network delays and platform limits can extend this. LinkedIn auth/errors/caps do not block YouTube, and YouTube upload failures do not block a ready opportunity's LinkedIn post.

## State, retries, and recovery

- Each `(opportunity_id, organization)` has one durable LinkedIn state. Publishing claims are atomic and committed before sending requests. Database backups include the LinkedIn outbox and attempt ledger.
- The attempt cap counts requests over a rolling 24-hour window, including rejected/ambiguous requests. The default is ten attempts per page per 24 hours and up to three successful posts per cycle. Provider quotas may be lower.
- HTTP 429 returns to pending with a bounded cooldown (numeric Retry-After, otherwise conservative handling). No rapid create retries.
- HTTP 401/403 or other definitive payload/version rejections block LinkedIn publishing for that page until resolved. Reauthorize/fix settings and run `python -m shorts.linkedin resume`; it resets only explicitly rejected entries.
- Network timeouts, HTTP 408/5xx, and a success response without a valid post ID stay uncertain. A crash after the claim leaves publishing state, which follows the same reconciliation path.
- The publisher searches up to 500 recent company posts for an exact author/commentary match. A single published match is reconciled; no match or multiple matches remain held. A bounded scan does not prove absence, so unresolved items are never blindly resent. Other candidates continue.
- Some apps receive refresh tokens, others do not. Granted refresh tokens are used when the access token expires; failed refresh or unavailable refresh requires renewed admin authorization. This is not perpetual authorization.
- HTTP and token errors avoid logging access tokens, client secrets, or raw credential responses. Tokens are stored locally as sensitive files; protect the laptop account and backup secrets separately.
- API version `202609` is configurable and must be maintained as LinkedIn versions sunset.

Use `python -m shorts.linkedin status` for queue records and `data/linkedin-health.json` for the separate health report. This does not change the main worker's YouTube health report. Do not run a manual LinkedIn cycle at the same time as another manual cycle; atomic claims prevent duplicate creates, but one worker is the supported deployment.

## Official references

- Posts API and organization permissions: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- Community Management access: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-api-migration-guide
- Programmatic refresh tokens: https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens
