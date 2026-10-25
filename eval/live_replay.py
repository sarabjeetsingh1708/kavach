"""Replay calls line by line through the live pipeline (rules every line, Evon in the background) and print
the level after each line. Run from kavach/: python -m eval.live_replay"""
import asyncio

from app.pipeline import CallSession

CALLS = {
    "scam: police threat, no money ask": [
        "Hello, Mumbai police cyber crime branch se bol rahe hain.", "Aapke number se illegal messages bheje gaye hain.",
        "Aapko giraftar kiya jayega jab tak aap cooperate nahi karte.", "Camera on rakhiye, aap hamari nigrani mein hain."],
    "genuine: police passport check": [
        "Namaste, main Kotwali police station se bol raha hoon.",
        "Aapke passport verification ke liye kal subah das baje thane aa jaiye.",
        "Apna Aadhaar card aur address proof saath laiye."],
    "genuine: bank fraud callback": [
        "Namaste, main aapke SBI branch se bol rahi hoon.",
        "Aapke card pe ek suspicious transaction dikh raha hai, kya yeh aapne kiya tha?",
        "Agar nahi, toh branch aakar ya 1930 pe report kijiye.", "Hum aapse OTP ya PIN kabhi nahi maangenge."],
}


async def replay(lines, gap_s=4.0):
    s = CallSession(send_alerts=False)
    timeline = []
    for line in lines:
        st = await s.add_text(line)
        timeline.append(f"{st['level']}({st['risk']})")
        await asyncio.sleep(gap_s)  # a sentence takes a few seconds; Evon answers in the background meanwhile
    st = s.state()
    timeline.append(f"-> end {st['level']}({st['risk']}) [rules {s.rule_risk}, evon {s.evon_risk}]")
    return " ".join(timeline)


async def main():
    for name, lines in CALLS.items():
        print(f"{name:36} {await replay(lines)}")


if __name__ == "__main__":
    asyncio.run(main())
