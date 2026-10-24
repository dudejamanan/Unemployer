# Partnerships and founder-led distribution

The private `outreach_contacts` table tracks organizations, public professional contact sources, category, outreach date, message status, follow-up date, response, outcome and partnership status. This project sends no outreach messages. Start with 15 campus/student-community prospects and 15 employers, researched deliberately from public professional pages. Do not scrape private contacts or invent audience figures.

Add a record:

```powershell
python -m shorts growth contact --organization "Example society" --category student_community --public-source https://example.org/team
```

Use `--contact` only for a deliberately verified public professional address. Private contacts are never exported to the hub.

## Editable student-community template

Hello [name], I run Unemployer, a source-linked internship and early-career discovery project. Could a relevant weekly shortlist be useful to [community]? Applications remain on original source pages. I can share a sample for your assessment. We make no placement or selection guarantee.

## Editable startup pilot template

Hello [name], are you recruiting interns or early-career applicants for [team]? Unemployer can help explain a verified opening to students. Please share the official role URL, eligibility, compensation period, location and deadline. Sponsorship would be disclosed and would not bypass checks. Would a small pilot be useful?

## Editable college-digest template

Hello [name], could a source-linked weekly internship shortlist support [college/team]? It would identify disclosed eligibility and deadlines, with applications going to original sources. Could we first compare a sample against your students' needs? Email delivery is not activated yet.

## Editable creator-collaboration template

Hello [name], your work on [specific topic] relates to Unemployer's student career guides. Would you consider a source-backed guide or checklist collaboration? We would agree attribution and reuse permission first, with no copied scripts or audience guarantees.

## Weekly operating routine

Inspect errors and source quality, compare content at similar ages, change one variable per experiment, and record responses and outcomes. Follow up appropriately and stop after a decline. Founder personal-profile publishing remains manual and is not connected to the company-page publisher.

## Future employer submissions

A future authenticated submission must include employer identity, official role URL, distribution authorization, compensation period, eligibility, work mode, deadline, verification evidence and sponsorship disclosure. Do not expose a public publish endpoint. Payment cannot bypass validation. Autonomous acceptance needs a separately tested policy; uncertain submissions stay deferred. A portal, payments, subscriptions and invoicing are out of scope.
