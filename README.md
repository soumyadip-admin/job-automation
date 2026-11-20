# SAM Career Job Discovery

A no-cost, review-first pipeline that collects recent public LinkedIn cards, trusted Naukri email-alert vacancies, six public Telegram job channels, and posts explicitly forwarded to `@SoumyadipSAMCareerBot`. It filters for realistic analyst/BI/MIS/reporting/WFM/operations-analytics roles and writes canonical records to the **Job Application Tracker** Google Sheet used by Sam Career Studio.

## Safety and truthfulness

- **No LinkedIn login, browser automation, challenge bypass, or auto-apply.**
- No vacancy is labelled `Applied` by this project.
- New records are `Discovered` when only title/source evidence is available, or `Review` when the available description supports the match.
- A Sheet authentication, spreadsheet-identity, worksheet, read, or row-write failure returns a nonzero exit code and makes GitHub Actions red.
- URLs are canonicalized before duplicate checks, so tracking parameters do not create repeat rows.
- Gmail is opened read-only and only recent mail from the `naukri.com` sender domain is parsed.
- The preflight write check creates, verifies, and immediately deletes a uniquely named one-cell diagnostic worksheet; it never edits tracker rows.
- Email receipt and Telegram message times are observation metadata, not automatically claimed as employer posting dates.
- Public Telegram channels use their no-login web previews; the automation never signs in to the user's personal Telegram account.
- Private-channel posts are read only when the user deliberately forwards them to the configured bot.
- Telegram sends one truthful hourly summary with new review links and counts. It never claims an application was submitted.

## Hourly workflow

`.github/workflows/job_automation.yml` runs at minute 17 of every hour. GitHub may start scheduled jobs a little late during busy periods.

Each run:

1. checks out the repository with `actions/checkout@v4`;
2. uses `actions/setup-python@v5`;
3. installs the small runtime dependency set;
4. runs the safety test suite;
5. checks that required secrets exist without printing them;
6. checks the Sheet's identity/read access and performs a reversible write test without touching tracker rows;
7. verifies that the token belongs to `@SoumyadipSAMCareerBot` and that the notification destination exists;
8. reads recent public Telegram posts and explicitly forwarded private posts;
9. discovers and saves duplicate-safe records, then sends one hourly summary.

Concurrency and a 20-minute timeout prevent overlapping/stuck runs.

## Required GitHub Actions secrets

Keep the existing values in **GitHub → repository Settings → Secrets and variables → Actions**:

- `GOOGLE_SHEETS_CREDENTIALS_JSON`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

The Telegram token must belong to `@SoumyadipSAMCareerBot`. After adding only the token secret, run **Telegram Pairing (one time)**. It sends the numerical chat ID privately to the bot conversation without printing it in Actions logs; add that number as `TELEGRAM_CHAT_ID`. Never paste the bot token into files, commits, screenshots, chat, or workflow logs. The expected spreadsheet title is `Job Application Tracker`; the expected tab is `Job_Applications`.

## Run locally (optional)

Set the six environment variables above plus `TELEGRAM_BOT_USERNAME=SoumyadipSAMCareerBot` in your own shell, then run:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/sheets_diagnostic.py
python main.py
```

Do not commit a `.env`, credential JSON file, password, access token, or generated log.

## Telegram sources

The public 24-hour scanner currently checks:

- `@seekeras`
- `@seekerascommerce`
- `@merademy`
- `@placementdriveofficial`
- `@jobskull`
- `@jobsgovind`

Social-only, webinar, course, “comment for link,” generic homepage, support/BPO and senior-role posts are rejected. Third-party links are followed to an official application page where possible. Official career pages that block automated checks are marked for browser review rather than falsely declared broken.

For a private channel or group, forward a concrete job post containing its application link to `@SoumyadipSAMCareerBot`. The bot only reads messages sent directly to it by the configured `TELEGRAM_CHAT_ID`.

## Tracker columns

The writer preserves the existing 11-column layout:

1. deterministic job ID
2. tracker observation time (Asia/Kolkata)
3. portal
4. title
5. company
6. canonical source/application URL
7. location
8. salary text
9. conservative match score
10. `Discovered` or `Review`
11. matched-skill/source metadata

## Important limitation

Public endpoints and email layouts can change or rate-limit requests. The workflow reports collection warnings and fails on required integration/write errors, but it cannot guarantee that every portal exposes 20 new jobs each hour. Sam Career Studio combines this Sheet with its other first-party/public sources to maintain its wider job radar.
