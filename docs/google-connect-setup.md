# Setting up "Connect Google" for the desktop app

This guide creates the Google credentials the app needs so the **Settings →
Integrations → Google → Connect** button actually links your Google account
(Docs, Gmail, Calendar).

The app's *code* is ready — it opens your real browser for the Google login and
brings the result back into the app. What's missing is a Google **OAuth client**
(an ID + secret that identifies Momentum to Google). You create that once in the
Google Cloud Console.

> One-time, ~15 minutes. You need a Google account. No coding.

---

## 1. Create a project

1. Go to <https://console.cloud.google.com/>.
2. Top bar → project dropdown → **New Project**. Name it `Momentum`. Create, then
   select it.

## 2. Turn on the APIs the app uses

Go to **APIs & Services → Library** and **Enable** each of these:

- **Google Docs API**
- **Google Drive API**
- **Gmail API**
- **Google Calendar API**

## 3. Configure the consent screen

**APIs & Services → OAuth consent screen**

1. User type: **External** → Create.
2. App name `Momentum`, your email for support + developer contact. Save.
3. **Scopes** — Add these (search by name):
   - `.../auth/documents`
   - `.../auth/drive.file`
   - `.../auth/gmail.readonly`, `.../auth/gmail.compose`, `.../auth/gmail.send`
   - `.../auth/calendar.readonly`, `.../auth/calendar.events`
4. **Test users** — add the Google account(s) you'll sign in with.

> **Important:** while the app is in "Testing", only the test users you list here
> can connect, and their access tokens expire weekly. That's fine for your own
> testing. Letting *anyone* connect requires submitting the app for Google
> verification (a separate, later step — needed before a public release because
> Gmail scopes are "sensitive/restricted").

## 4. Create the OAuth client

**APIs & Services → Credentials → Create credentials → OAuth client ID**

- Application type: **Web application** (it supports the fixed `localhost`
  redirect the app uses).
- Name: `Momentum desktop`.
- **Authorized redirect URIs** → Add:
  `http://localhost:8000/api/v1/integrations/google/callback`
- Create. Copy the **Client ID** and **Client secret**.

## 5. Plug the credentials in

**For local dev** (`npm run dev` + the Python backend): put them in
`backend/.env`:

```
GOOGLE_CLIENT_ID=<your client id>
GOOGLE_CLIENT_SECRET=<your client secret>
# Optional — defaults to the value below, which matches the redirect URI above:
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/integrations/google/callback
```

Restart the backend, open Settings → Integrations → Google → **Connect**. Your
browser opens, you approve, and the app flips to "connected" when you return.

**For the installed desktop app:** the bundled backend doesn't read your
`backend/.env`, so the credentials have to be baked into the build. That's a
small build-step we'll add once you've created the client above — tell Claude
"the Google client is ready" and it'll wire the build to include them.

> Note: for a desktop/installed app, Google treats the client secret as
> *not confidential* (it ships inside the app). That's expected and supported for
> this OAuth client type.

---

## Troubleshooting

- **"Couldn't connect Google" with a message about credentials** → the backend
  has no `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (step 5).
- **Google shows "Access blocked: app is being tested"** → add your account under
  **Test users** (step 3.4).
- **`redirect_uri_mismatch`** → the redirect URI in step 4 must match
  `GOOGLE_REDIRECT_URI` exactly (including `http`, port `8000`, and path).
