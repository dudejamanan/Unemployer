# Temporary LinkedIn image hosting

The existing Unemployer hub now provides a small image hosting service backed by a Sites-managed R2 bucket. It is intended for the worker's generated opportunity cards, not anonymous uploads.

## Automatic flow

1. Select a fresh eligible opportunity under the existing LinkedIn cadence/caps.
2. Render its 1200 × 628 card from source facts.
3. Upload the PNG through an authenticated PUT and record its stable content-hash URL in SQLite.
4. Attach that public URL to Buffer's `createPost` image asset, alongside the existing caption/application link.
5. Retain the source image while Buffer reports accepted/scheduled, an error, or an uncertain outcome.
6. Once Buffer confirms `sent`, mark the existing outbox posted and DELETE the hosted source image.
7. Retry failed cleanup after 15 minutes without recreating the post. Reconciliation/cleanup runs independently of posting cadence, including weekends.

Deleting the hosted source does not remove the image already copied into the LinkedIn post. There is no time-based deletion for unresolved deliveries: expiring queued media could break publication. If the laptop is offline, cleanup resumes when the worker returns. Locally rendered previews remain under ignored `out/linkedin/` for recovery.

## Service interface

- `PUT /media/<sha256>.png`: Bearer-authorized, content hash verified, PNG only, 1200 × 628 pixels, at most 2 MiB. Repeat uploads of identical bytes are idempotent.
- `GET` / `HEAD` at that URL: public image access, no cookies/login needed, no-store headers.
- `DELETE` at that URL: Bearer-authorized and idempotent; subsequent reads return 404.
- No public upload form, object-listing route, arbitrary URL-fetch endpoint or browser-side secret.

Runtime secret `MEDIA_WRITE_KEY` is configured on Sites and in the ignored local `.env`; never put it into a URL, source file, caption or chat. `MEDIA_HOST_URL` is the HTTPS origin. Names only are documented in `.env.example`. Secret rotation needs both the local worker and Sites value updated, followed by deployment of the new environment revision.

`linkedin.image_cards: true` enables opportunity-image attachments; false keeps the original text-only transport. Research-guide text posts are currently unchanged. Card generation/hosting is attempted up to three times. If all attempts fail, a persistent per-post fallback sends the existing caption and application link without an image. An explicitly rejected image-asset create can retry once as text-only; accepted or uncertain creates are reconciled, never duplicated. Cleanup failures do not block posting. The additive `linkedin_media` table preserves the URL/local path/state/cleanup error; old outbox/publication records are not reset. Images shared by unresolved records are retained until they are safe to delete.

## Inspect and test

```powershell
python -m shorts.linkedin status
Get-Content data/linkedin-health.json
python -m pytest tests/test_media_host.py tests/test_buffer_api.py tests/test_linkedin_card.py -q
```

At the site checkout run `node scripts/test-media.mjs`. It covers authentication, upload/read/delete, repeat writes/deletes, invalid images and size limits with mock storage. Live deployment smoke tests separately verify the actual storage binding and public fetch/deletion lifecycle. No social post is created by those tests.

Source changes: `shorts/media_host.py`, `shorts/buffer_api.py`, `shorts/linkedin.py`, `shorts/linkedin_card.py`, `sites/unemployer/worker/media.js`, hosted route integration and the R2 manifest binding. The Python worker needs restarting after code/credential changes. The hosting service runs independently of the laptop, while publishing and deletion reconciliation still use the local worker.

## Verified deployment

Deployed on 24 October 2026 as hub version 4. Live tests returned unauthenticated PUT 401, authenticated PUT 201, byte-identical public GET 200, DELETE 204, then GET 404. The regression suite passed 188 tests with 6 skipped; 21 focused card/Buffer/media tests also passed after the availability check. Automatic opportunity cards are enabled and the Windows worker was restarted. No live social post was forced for testing; the normal weekday/spacing rules remain active.

Image fallback policy: three preparation attempts, then text-only. The fallback is stored in `linkedin_media_fallback`, so restarts and provider cooldowns do not repeat failed image work. Authentication failures, platform quotas and uncertain social submissions retain their existing protections; an optional image failure is not allowed to block a text post.
