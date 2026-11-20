# Beginner Upload Guide

This package contains no passwords, access keys, tokens, Sheet data, or generated logs.

## Important

GitHub's website does **not** unpack a ZIP inside a repository. First extract this ZIP on your device. Upload the files and folders inside the extracted `job-automation-main` folder—not the ZIP itself and not an extra outer folder.

The workflow is inside the hidden-looking path:

`.github/workflows/job_automation.yml`

If the `.github` folder does not appear during browser drag-and-drop, do not create a second workflow elsewhere. On GitHub use **Add file → Create new file**, enter `.github/workflows/job_automation.yml` as the filename, and copy the matching file's contents from this package.

Before the first full run, add `TELEGRAM_BOT_TOKEN` for `@SoumyadipSAMCareerBot` under **Settings → Secrets and variables → Actions**. Then manually run **Telegram Pairing (one time)**. The bot—not the public Actions log—will send you your private numerical chat ID. Add that number as the `TELEGRAM_CHAT_ID` Actions secret. Keep the existing Sheets and Gmail secrets. Enter secret values directly in GitHub; never paste the bot token into chat, files, commits, or screenshots.

After the files and secrets are ready, open the repository's **Actions** tab and run **SAM Career Job Discovery** once with **Run workflow**. A green run confirms the tests, Sheet preflight, Gmail connection, Telegram bot identity/destination, source collection, Sheet writes and hourly summary. A red run is intentional when a required integration fails; open the failed step but never post its secret values.
