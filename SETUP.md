# Setup, step by step

You need three free accounts: FRED, GitHub, Cloudflare. About 30 minutes.

## 1. FRED API key
1. https://fredaccount.stlouisfed.org/login/secure/ > Create new account, confirm the email.
2. https://fredaccount.stlouisfed.org/apikeys > Request API Key. Description: `hours-of-work site`.
3. Copy the 32-character key somewhere private.

## 2. Put the files on GitHub
1. Unzip `labor-hours.zip`.
2. Go to https://github.com/new. Repository name `hours-of-work`. Public. Leave every checkbox unticked. Create repository.
3. Click the link **uploading an existing file**.
4. Open the unzipped folder, select everything inside it, drag it into the browser window. Wait for the list to finish, scroll down, click **Commit changes**.

## 3. Cloudflare token and account ID
1. https://dash.cloudflare.com > bottom-left of the sidebar, click your profile icon > **Profile** > **API Tokens** > **Create Token**.
2. Next to **Edit Cloudflare Workers** click **Use template**. Leave the defaults. **Continue to summary** > **Create Token**.
3. Copy the token now (it is shown once).
4. In the dashboard sidebar click **Workers & Pages**. Copy the **Account ID** from the right-hand panel.

## 4. Add three secrets in GitHub
Repo > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**. Add:
- `FRED_API_KEY` = your FRED key
- `CLOUDFLARE_API_TOKEN` = the Cloudflare token
- `CLOUDFLARE_ACCOUNT_ID` = the account ID

## 5. Add the scheduler
Repo > **Add file** > **Create new file**. In the name box type exactly `.github/workflows/update.yml`. Open `deploy-workflow/update.yml` in the repo, copy its whole contents, paste into the editor. **Commit changes** > **Commit directly to the main branch**.
This starts the first run automatically.

## 6. Watch the first run
Repo > **Actions** tab > click the top run. A green check after ~1-3 minutes means it worked. Red X: open the run, click the job, expand the red step, copy the text, and send it to Claude.

## 7. Open your site
Cloudflare dashboard > **Workers & Pages** > **hours-of-work** > **Visit**. The yellow "Sample data" banner should be gone.

## 8. Optional but recommended
Repo > Settings > Secrets and variables > Actions > **Variables** tab > New repository variable: `SITE_URL` = your site address (no trailing slash). If one source fails some day, the site then keeps yesterday's copy of that item, flagged as stale.

## Monthly chore: new vehicle prices
Add one row to `data/manual/new_vehicle_atp.csv` (on GitHub: open the file, click the pencil icon) after each monthly Kelley Blue Book report.
