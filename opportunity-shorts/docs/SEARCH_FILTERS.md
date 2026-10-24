# Website search filters

The hub now supports combined role/company/skill keyword search (all words), opportunity type, remote/hybrid/explicit on-site/unknown work arrangement, company, city/region, skills mentioned, compensation disclosure, minimum monthly INR pay, application deadline, source and last-checked freshness. Users can sort by role name, highest monthly INR pay, deadline or last check; active-filter counts, reset and actionable empty results are included. The existing brand and responsive layout are preserved.

Accuracy boundaries:

- Bangalore/Bengaluru and Gurgaon/Gurugram are search aliases.
- False/absent remote flags are not presented as proof of an on-site job. Unknown arrangement remains searchable separately.
- Skills are a bounded whitelist matched in source titles/descriptions, not claims of required qualifications. Java and JavaScript are matched separately. The public API returns only skill names, not full source descriptions.
- Minimum pay compares the lower disclosed INR monthly amount; annual, foreign-currency, undisclosed and “up to” values do not satisfy the threshold. A range of INR 20,000–100,000 cannot match a minimum of INR 30,000. Other source compensation text remains visible unchanged.
- Missing deadlines and check times cannot satisfy their respective date filters. Last checked is explicitly separate from posting date. Expired listings stay excluded.
- No graduation-year, nationality, experience or duration eligibility is fabricated from unavailable data. Verify detailed requirements at the original application page.
- Filters/search text stay in the browser. Existing optional aggregate analytics do not receive raw query, location, skill or company values.

Shared behavior is in `sites/unemployer/worker/search.js`, embedded into the hosted worker and browser by `scripts/prepare_hub.py`. Snapshot extraction exports only named skills from source text. New source data continues to use existing public feeds and dated fallback rules. The image hosting routes and R2 binding remain intact.

Validation: Node search tests cover combined filters, aliases, exact skill mentions, range/period pay interpretation, missing fields, expiration and sorting. Existing hub safety, guide/digest/privacy and image hosting tests passed. Playwright tested combined filters, zero results, reset, JavaScript errors and mobile overflow using controlled response fixtures, not invented production listings. Screenshots are stored under ignored `out/growth/search-desktop.png` and `search-mobile.png`.

Run from `sites/unemployer`: `node scripts/test-search.mjs`. Build with `python scripts/prepare_hub.py` from the application root, then the existing Sites build/validation/deployment workflow.
