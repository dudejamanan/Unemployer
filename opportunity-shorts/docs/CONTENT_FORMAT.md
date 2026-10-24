# Enriched opportunity breakdown

Editorial version: `unemployer-editorial-3`.

The five scenes are: factual compensation/company/role opening; location, compensation and available eligibility; collected source excerpt and a conditional plain-English term explanation; role-specific general application advice; application-link next step. A disclosed stipend can lead the spoken hook. No salary conversion, selection guarantee, or fabricated deadline is introduced.

Source evidence is generated deterministically from the collected description, never by the LLM. It is a contiguous normalized-text excerpt capped at 190 characters, with an ellipsis when truncated. The source domain and collection date are displayed. Collection date is not proof of employer legitimacy or a new live verification. Empty descriptions get an explicit source-page fallback. The small term explainer appears only when the term is present in the collected description and is labelled general explanation. Advice is explicitly distinguished from employer requirements.

Scene shares are approximately 10%, 22%, 28%, 25%, and 15% of the narration duration. Assembly snaps boundaries to nearby word timings; captions continue through cuts. The evidence and source details appear above the caption/YouTube UI safe areas. Five-scene specs and actual assembly use matching target fractions.

The male Indian-English narrator is consistent across new builds. Local Ollama still writes the narration; script fact/link checks and output duration/layout guards remain. Changing editorial identity invalidates unpublished old builds. Already published videos are preserved. New scene templates also invalidate visual caches.

Create an unpublished preview with `python scripts/preview_enriched.py <opportunity-id>`. It saves video.mp4, script.json, source-evidence.json and preview.json under `out/enriched-preview-<id>`. It does not change publishing state or upload the video. Existing automatic posting cadence remains unchanged after validation.

This release adds the opportunity-breakdown format only. Weekly digests, application-tutorial episodes and retention-based experiments remain future work. No near-identical hook variants are automatically published.

## Opening frame and thumbnail

The first scene is a cover with large disclosed compensation, role name, company and location. INR formatting is presentation-only and preserves ranges and “up to” qualifiers; unknown compensation is never invented. Each render exports the same cover to `thumbnail.png`. Automatic uploads attempt YouTube `thumbnails.set` after the video succeeds when `upload.set_thumbnail` is enabled. A rejected/unsupported thumbnail does not trigger another video upload. Results are recorded in `thumbnail-upload.json`. Shorts thumbnail support and display depend on YouTube/channel eligibility; when unavailable, select the opening frame through the YouTube app or eligible Studio controls. The existence of the first frame does not force YouTube to select it automatically. Manual export bundles include the PNG.
