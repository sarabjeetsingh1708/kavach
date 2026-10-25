# How to start Kavach

Kavach runs on a laptop and reaches the phone through a free Cloudflare tunnel: two terminals, then one tap on
the phone. Commands are for Windows PowerShell, run from the `kavach` folder.

## Quick start

If the one-time setup below is done, this is all you need:

1. **Terminal 1, the server:**
   ```powershell
   .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   Wait for `Application startup complete`.
2. **Terminal 2, the tunnel:**
   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
   Copy the `https://…trycloudflare.com` address it prints.
3. **Phone:** open that address in Chrome, then tap the installed **कवच** icon. If the address changed since
   last time, install the app again (step 3 below).

Keep both terminals open while you use Kavach. The laptop must stay on.

## One-time setup

1. **Python packages** (Python 3.10 or newer):
   ```powershell
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
2. **The `.env` file:** copy `.env.example` to `.env` and fill it in. Never commit or share it.
3. **Cloudflare tunnel tool:**
   ```powershell
   winget install Cloudflare.cloudflared
   ```

What goes in `.env`:

| Setting | Needed for | Where it comes from |
|---|---|---|
| `GNANI_API_KEY` | Everything (Prisma listens, Timbre speaks) | app.gnani.ai → API keys, with both Speech to Text and Text to Speech scopes |
| `TELEGRAM_BOT_TOKEN` | Family alerts and the voice-note bot | @BotFather on Telegram → `/newbot` |
| `KAVACH_UPLOAD_TOKEN` | Auto-checking call recordings | Any long random string |
| `EVON_URL`, `EVON_API_KEY` | Evon (optional; the rules work without it) | Printed by the Kaggle notebook, see below |
| `LANGUAGE` | Default language for Telegram and recordings | `hi-IN` (the app's language picker overrides it per phone) |

## Step 1: start the server (terminal 1)

```powershell
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

It's ready when it prints `Application startup complete` and `Uvicorn running on http://127.0.0.1:8000`. The
first start takes a few seconds longer while it prepares the spoken warnings in all four languages; after that
they come from the `cache` folder.

The Telegram bot starts inside this same server when `TELEGRAM_BOT_TOKEN` is set, so there's nothing extra to run.
Open http://localhost:8000 on the laptop to try it before involving the phone.

## Step 2: start the tunnel (terminal 2)

The phone can't reach `localhost` on your laptop, and Chrome only allows the microphone and "Install app" on an
HTTPS address. A free Cloudflare quick tunnel gives you one:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

After a few seconds it prints an address like `https://quiet-river-1234.trycloudflare.com`. That's the address
for the phone.

- **Use `127.0.0.1`, not `localhost`.** With `localhost`, cloudflared tries the IPv6 address `[::1]`, which the
  server doesn't listen on, and every request fails with "connection refused".
- **The address changes every time the tunnel restarts.** A fixed address needs a Cloudflare account plus your
  own domain.
- **Don't post the address publicly.** Anyone who has it can use the page, and their calls spend your Gnani
  credits. Recording checks are protected by `KAVACH_UPLOAD_TOKEN`; the page is not.

## Step 3: open and install the app on the phone

Use a **spare phone or tablet**, not the phone taking the call: Android silences other apps' microphones during
a call. The spare phone listens to the call phone on speaker.

1. Open the tunnel address in **Chrome**.
2. Tap **⋮ → Install app** (on some phones: **Add to Home screen → Install**). On an iPhone, use Safari:
   **Share → Add to Home Screen**.
3. Open **कवच** from the home screen. It opens full-screen.
4. On first launch, **pick a language**: हिंदी, தமிழ், বাংলা or English. It sets the screen text, what Prisma
   listens for, and the spoken warning; the phone remembers it, and the 🌐 chip changes it later.
5. Tap the big listen button once and **allow the microphone**.

After a tunnel restart, the installed icon still points to the old address: open the new address in Chrome and
install again.

## Optional: start Evon on Kaggle

Evon judges the whole conversation and catches scams the rules miss, like a police threat with no money request
yet. Kavach works without it, using the rules alone. Evon is too big for a laptop (18 GB), so it runs free on
Kaggle's two T4 GPUs.

1. On kaggle.com (phone-verified account), create a notebook, then **File → Import Notebook** →
   [`evon/kavach_evon_kaggle.ipynb`](../evon/kavach_evon_kaggle.ipynb).
2. In the right panel set **Accelerator: GPU T4 x2** and **Internet: on**.
3. Click **Run All**. The first run takes about 35 minutes: about 30 to build the server, about 5 to download
   the model.
4. The last cell prints two lines. Paste them into `.env`:
   ```
   EVON_URL=https://…trycloudflare.com/v1/chat/completions
   EVON_API_KEY=…
   ```
5. **Restart the Kavach server** (Ctrl+C in terminal 1, then the same command). Check it with
   `.venv\Scripts\python -m app.evon_judge`.

A Kaggle session ends after about 12 hours or when idle; re-run it and paste the new lines. To skip the
30-minute build next time: after a successful run, **Save Version → Save & Run All (Commit)**; next session,
**Add Input → Your Work** → this notebook, then Run All.

## Optional: family alerts, the voice-note bot and recording checks

These need `TELEGRAM_BOT_TOKEN` in `.env`. The bot runs inside the server from step 1.

- **Family alerts:** the son or daughter opens the bot in Telegram and sends **`/guardian`** once. From then on,
  any call that turns red sends them the scam type, risk score, reasons and what was said. The app's header
  shows "family alerts on" when this is set up.
- **Voice-note bot:** anyone forwards a call recording or WhatsApp voice note to the bot. It replies with a red,
  orange or green verdict and the spoken warning. Only the first 5 minutes are checked.
- **Auto-checking recordings on the parent's own phone:** the phone records calls, and the free MacroDroid app
  sends each new recording to `https://<tunnel address>/check-recording` with the `X-Kavach-Token` header. Full
  setup, folder paths by phone brand and a test command: [auto-check-recordings.md](auto-check-recordings.md).
  The MacroDroid steps haven't been tried on a real phone yet.

## Check it works

1. **Health:** open `http://localhost:8000/health` on the laptop. `gnani_key: true` is required; `evon`,
   `telegram_bot` and `guardian` show whether the optional parts are set up.
2. **Demo call:** in the app, open the demo drawer and tap the fake CBI officer. Within about 10 seconds the
   screen turns red, the warning plays in the chosen language, and (with `/guardian` set up) the family's
   Telegram gets an alert.
3. **Real call:** play or speak a scam line on another phone, on speaker, with Kavach listening nearby. For
   example: *"Main CBI se bol raha hoon, aapke naam pe arrest warrant hai, kisi ko mat batana, abhi paise transfer
   kijiye."* The rings around the button should pulse with the voice, and captions appear within about 5 seconds.

Developers can also run `.venv\Scripts\python -m pytest` (13 tests) and `.venv\Scripts\python -m eval.smoke_test`
(one real Timbre → Prisma round trip).

## Troubleshooting

Most of these came up while building Kavach; the last two are known limits of the setup.

| What you see | Cause | Fix |
|---|---|---|
| Tunnel prints "Unable to reach the origin service … [::1]:8000 … refused" | The server isn't running, or the tunnel used `localhost` (IPv6) | Start step 1 first; run the tunnel with `http://127.0.0.1:8000` |
| Phone shows the old icon or old page after an update | Android cached the old icon | Uninstall the app; Chrome → Settings → Site settings → All sites → the tunnel address → Clear & reset; install again; restart the phone if still old |
| Installed app stopped loading | The tunnel restarted, so the address changed | Open the new address in Chrome and install again |
| Server log: "Conflict: terminated by other getUpdates request" | Two servers are running the same Telegram bot | Run only one server; a second (test) server needs `KAVACH_NO_BOT=1` |
| Server log: "[evon] falling back to rules" | The Kaggle session ended or its address changed | Re-run the notebook, paste the new `EVON_URL` and `EVON_API_KEY`, restart the server. Kavach keeps working on the rules meanwhile |
| "Prisma 429 RATE_LIMITED" | Gnani allows one active speech-to-text request per key | Already handled: Kavach queues requests and retries. Don't run other tools on the same key at the same time |
| "Microphone or server not available" in the app | Mic permission denied, or the page isn't on HTTPS | Allow the microphone for the site in Chrome; use the tunnel address, not the laptop's IP |
| Live listening hears nothing during a call | It's running on the same phone as the call | Use a second phone or tablet next to the call phone, on speaker |

## Stopping, and restarting later

Press **Ctrl+C** in both terminals. Nothing is stored except the cached warning clips, so nothing needs saving.

Next time, repeat steps 1 to 3. What stays and what changes:

| Part | After a restart |
|---|---|
| `.env` keys, family alert (`/guardian`), language choice on the phone | Stay as they were |
| Tunnel address | **New every time:** open it in Chrome and install the app again |
| Evon on Kaggle | Ends after about 12 hours: re-run the notebook and paste the new two lines into `.env` |
| Recording checks (MacroDroid) | Update the tunnel address in the MacroDroid macro |
