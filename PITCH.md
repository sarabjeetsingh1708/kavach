# Kavach: AI scam-call shield for Indian families

**Sarabjeet Singh · Solo entry · Great Indian AI Internship Challenge**

## The problem
Phone fraud in India (digital arrest, fake KYC, courier and customs threats, fake-relative emergencies) works through fear and urgency. Elderly parents are the main targets. The calls come in Hindi and Hinglish over noisy phone lines, and families usually find out only after the money is gone.

## The solution
Kavach listens to a suspicious call on speaker and warns the parent out loud, in their own language, before they share an OTP or send money. It also sends their son or daughter a Telegram alert with the scam type, risk score and reasons. Warnings are spoken in Hindi, Tamil, Bengali and English.

**Users:** the parent hears the warning and needs no setup; the son or daughter installs it once and gets the alerts.

**Three ways to use it, all free:** live listening on a spare phone near the call; auto-checking call recordings sent from the parent's phone; and a Telegram bot that takes a forwarded recording or voice note and replies with a verdict and a spoken warning.

## How it uses Gnani AI models
- **Prisma (speech to text):** transcribes the noisy, code-mixed call audio.
- **Evon (reasoning):** judges the full transcript about every 10 seconds and returns a risk score, scam type and reasons as JSON. It runs on Kaggle T4 GPUs; if it is unavailable, the rules layer decides alone.
- **Timbre (text to speech):** speaks the warning in four languages, from cached clips so it plays instantly.

A rules layer scores red-flag phrases (OTP, arrest threats, "tell no one") on every audio chunk. A red alarm fires at risk 70 or above; 40 to 69 gives a softer "be careful" prompt.

## Results on synthetic calls
66 scripts (30 scam, 30 everyday, 6 hard negatives that sound official) at four noise levels: 264 calls. False alarms are out of 36 genuine calls.

| Noise (SNR) | Scams caught | False alarms | Prisma WER (English) |
|---|---|---|---|
| Clean | 97% | 1 (3%) | 5% |
| 20 dB | 100% | 1 (3%) | 6% |
| 10 dB | 100% | 1 (3%) | 7% |
| 5 dB | 100% | 1 (3%) | 11% |

## Honest limits
- All calls are synthetic (Timbre voices with generated noise), and one person wrote the scripts and the rules, so these numbers are optimistic.
- The hard negatives were added after the first Evon run, so they are not a clean held-out test.
- One genuine bank-callback call still triggers a false red alarm; I chose not to tune it away.
- The Tamil and Bengali warnings need review by native speakers.
- Kavach is an aid, not a guarantee.

## Links
- Code: https://github.com/sarabjeetsingh1708/kavach
- Demo video: https://www.youtube.com/watch?v=fZpOKIOwnpo
- X post: https://x.com/sarabjeet178/status/2114385309391810618
- LinkedIn post: [PASTE LINK]
