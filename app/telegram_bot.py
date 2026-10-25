"""Mode B: send a call recording / WhatsApp voice note to the bot -> text verdict + Timbre voice warning.
Also: /guardian registers this chat to receive live alerts from the web app.
Runs inside the web server when TELEGRAM_BOT_TOKEN is set; or standalone: python -m app.telegram_bot"""
import io

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from . import alerts, config, gnani_tts
from .alerts import LABELS
from .pipeline import CallSession

DISCLAIMER = "Kavach is an aid, not a guarantee. Report fraud on 1930."


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Namaste! Main Kavach hoon. 🛡️\n\n"
        "Kisi suspicious call ki recording ya voice note bhejiye, main bataunga ki yeh fraud hai ya nahi.\n"
        "Send me a call recording or voice note and I'll tell you if it looks like a scam.\n\n"
        "Son/daughter? Send /guardian to get live alerts when Kavach detects a scam call on your parent's phone.\n\n"
        + DISCLAIMER)


async def guardian(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    alerts.set_guardian(update.effective_chat.id, user.full_name if user else "")
    await update.message.reply_text(
        "✅ You are now the guardian. When Kavach hears a scam call, you'll get an alert here "
        "with the scam type, risk score and reasons.")


async def handle_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = update.message
    media = m.voice or m.audio or m.document
    duration = getattr(media, "duration", None)
    long_note = (f" (only the first {config.MAX_AUDIO_S // 60} minutes are checked)"
                 if duration and duration > config.MAX_AUDIO_S else "")
    await m.reply_text(f"सुन रहा हूँ... 🎧{long_note}")
    audio = bytes(await (await media.get_file()).download_as_bytearray())
    print(f"[bot] audio from chat {update.effective_chat.id}: {len(audio)} bytes, "
          f"{getattr(media, 'mime_type', '?')}, {duration}s")
    try:
        st = await CallSession(send_alerts=False).add_audio(audio, final=True)
    except Exception as e:
        print(f"[bot] analysis failed: {e}")
        await m.reply_text(f"Sorry, could not analyse this audio: {e}")
        return
    print(f"[bot] verdict {st['level']} risk={st['risk']} type={st['scam_type']} heard={st['transcript'][:120]!r}")
    icon = {"danger": "🔴", "caution": "🟠", "safe": "🟢"}[st["level"]]
    label = LABELS.get(st["scam_type"], "Call") if st["level"] != "safe" else "Looks like a normal call"
    reasons = "\n".join(f"• {r}" for r in st["reasons"][:4]) or "• No red flags found"
    heard = st["transcript"][:400] or "(no speech recognised)"
    await m.reply_text(f"{icon} {label} (risk {st['risk']}/100)\n{reasons}\n\nWhat I heard:\n\"{heard}\"\n\n{DISCLAIMER}")
    if st["warning_text"]:
        lang = st["language"]
        voice = await gnani_tts.synthesize(gnani_tts.warning_for(st["level"], st["scam_type"], lang), lang)
        if voice:
            await m.reply_audio(io.BytesIO(voice), filename="kavach-warning.wav", title="Kavach warning")
        else:
            await m.reply_text(st["warning_text"])


def build() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("guardian", guardian))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.Document.AUDIO, handle_audio))
    app.add_error_handler(on_error)
    return app


async def on_error(update, ctx: ContextTypes.DEFAULT_TYPE):
    print(f"[bot] error: {ctx.error!r}")


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env (create a bot with @BotFather).")
    build().run_polling()


if __name__ == "__main__":
    main()
