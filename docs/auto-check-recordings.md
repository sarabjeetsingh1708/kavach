# Auto-check call recordings on the parent's own phone (free)

Most Android phones sold in India can record calls automatically. With a free automation app, every new
recording is sent to Kavach as soon as the call ends. Kavach checks it with Prisma, the rules and Evon. If it
looks like a scam, the family gets a Telegram alert, and the parent's phone can show a Hindi warning.

**What this gives you:**
- **No new app to build, no Play Store, no money.**
- **The warning comes after the call, not during it.** Many scams run over several calls ("I'll call back
  with the verification steps"), so the family can step in before the money is sent.
- **Privacy:** recordings go to your own Kavach server. The audio is transcribed by Gnani's Prisma API, and the
  transcript is judged by your own Evon server. Kavach itself keeps nothing after replying. You can limit it to
  calls from unknown numbers (see step 4).

> **Not yet tested on a real phone.** The Kavach side is tested: an M4A recording sent the way an automation
> app would gets a verdict in about 6 s, plus the Telegram alert. The phone steps below follow MacroDroid's
> documented features, but I could not check every menu name. If a step looks different on your phone, the
> idea is the same: *when a file appears in the recordings folder, POST it to Kavach*.

---

## 1. Turn on automatic call recording on the parent's phone

The setting is in the Phone/Dialer app, usually under **Settings → Call recording → Record calls automatically**.
Then find where the recordings are saved. Open the **Files** app and look for:

| Brand | Usual folder |
|---|---|
| Xiaomi / Redmi / POCO | `MIUI/sound_recorder/call_rec` (Xiaomi's documented path) |
| Samsung | `Recordings/Call` or `Call` |
| Realme / OPPO / OnePlus / Vivo | something like `Recordings/Call Recordings`, `Music/Recordings`, or `Record/Call` |

**Phones using the Google Phone app** (Pixel, Motorola, recent OnePlus/Nokia) keep recordings *inside the app*,
where other apps can't reach them. On those phones, use the manual way: share the recording to the Kavach
Telegram bot.

## 2. Give Kavach a public address (free)

The phone needs to reach the Kavach server on your laptop. On the laptop, install Cloudflare's free tunnel
tool once, then start it while Kavach is running:

```bash
winget install Cloudflare.cloudflared
```
```bash
cloudflared tunnel --url http://localhost:8000
```

It prints an address like `https://something-random.trycloudflare.com`. **The address changes every time the
tunnel restarts**, so update it in step 4 when it does. The same address also serves the installable web app.

## 3. Test from the computer first

Your secret upload token is the `KAVACH_UPLOAD_TOKEN` line in `kavach/.env`. Don't share it: anyone who has it
can spend your Gnani credits. Send any audio file you have to the server:

```bash
curl -X POST "https://YOUR-ADDRESS.trycloudflare.com/check-recording" -H "X-Kavach-Token: YOUR-TOKEN" -H "X-Filename: test.m4a" --data-binary "@some-recording.m4a"
```

You should get back JSON with `"level"` (`safe`, `caution` or `danger`) and a Hindi `"notify"` line. A scam
recording also triggers the Telegram alert.

## 4. Set up MacroDroid on the parent's phone

Install **MacroDroid** (free on the Play Store; the free version allows a few macros, which is plenty), then create
a new macro:

**Trigger: File Changed**
- Folder: the recordings folder from step 1
- Option: *File created*
- When asked, allow MacroDroid **file access**. On Android 11+ this is "Allow management of all files".

**Action: HTTP Request**
- Method: **POST**
- URL: `https://YOUR-ADDRESS.trycloudflare.com/check-recording`
- Header: `X-Kavach-Token` = your token
- Body: the file that triggered the macro (MacroDroid offers the trigger's file path as a variable). Kavach
  accepts either the file as the raw body or a multipart upload with a field named `file`.
- Save the response into a variable, e.g. `kavach_reply`.

**Optional action: show the warning on the parent's phone**
- *If* `kavach_reply` contains `danger`, then **Display Notification** (or **Speak Text**) with:
  `⚠ कवच: पिछली कॉल फ्रॉड लग रही थी। किसी को पैसे या OTP मत दीजिए।`

**Optional constraint: unknown numbers only.** Many recorders name files after the contact
(`Mummy_20261025...m4a`) or the number (`+9198...`). If yours does, add a constraint so only files whose
name starts with a digit or `+` are sent. This saves credits and keeps family calls private.

## 5. Try it

Call the parent's phone from a number not saved in their contacts and act out a scam: *"Main CBI se bol raha
hoon, aapke naam pe arrest warrant hai, kisi ko mat batana..."*. Hang up. Within about a minute (the time for
the recorder to save the file, plus about 6 s for Kavach), the family's Telegram should get the 🚨 alert
marked *recorded call*.

## Limits, stated plainly

- **Only the first 5 minutes** of each recording are checked (`MAX_AUDIO_S` in `.env`), to protect credits.
  A 5-minute call is about 50 Prisma requests, sent one at a time; Gnani allows one active request per key.
- **The laptop must be on**, with Kavach and the tunnel running.
- **Some phones announce** "this call is being recorded" to both sides. That's the phone's rule, not Kavach's.
- **Auto-recording calls** may require the other party's consent where you live. Check before relying on it.
