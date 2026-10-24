# LinkedIn opportunity cards

Generate a 1200 × 628 PNG and its matching post caption from an existing opportunity:

```powershell
python -m shorts.linkedin_card --id OPPORTUNITY_ID
python -m shorts.linkedin_card --id OPPORTUNITY_ID --output out/linkedin/preview.png
python -m pytest tests/test_linkedin_card.py -q
```

The reference-inspired design uses a dark background, orange serif role title, restrained Unemployer branding and location/type/pay facts. Long titles wrap and resize; missing facts are labelled, not invented. Pay qualifiers and periods are preserved. Duration and full-time status are not inferred from the word internship. Listing availability, rejection and scam checks run before CLI export. Source links and complete caveats remain in the generated caption.

Current status: reusable local renderer and caption export implemented, four focused tests passed, real listing preview visually checked. The temporary image host and automated Buffer attachments are now implemented; see [MEDIA_HOSTING.md](MEDIA_HOSTING.md).

Autonomous image attachments use the existing hub with authenticated upload/delete and public image reads. Buffer accepts `assets: [{image: {url: "https://.../card.png"}}]`; it cannot upload a local PNG directly. URLs must remain public through actual delivery. See https://developers.buffer.com/guides/hosting-media and https://developers.buffer.com/examples/create-image-post.html. Do not use expiring URLs, private Drive links, or assume a local output path is remotely accessible. No new paid service or hosting credential has been introduced.
