"""Spot-check: genuine calls that sound official (police, bank, courier) must not trigger the red alarm.
Run from kavach/: python -m eval.legit_calls_check"""
import asyncio

from app import evon_judge, rules

CALLS = {
    "police_opening_only": "Hello, Mumbai police cyber crime branch se bol rahe hain.",
    "real_passport_verification": "Namaste, main Kotwali police station se bol raha hoon. Aapke passport verification ke "
                                  "liye kal subah das baje thane aa jaiye. Apna Aadhaar card aur address proof saath laiye.",
    "real_bank_fraud_callback": "Namaste, main aapke SBI branch se bol rahi hoon. Aapke card pe ek suspicious transaction "
                                "dikh raha hai. Kya yeh aapne kiya tha? Agar nahi, toh branch aakar ya 1930 pe report "
                                "kijiye. Hum aapse OTP ya PIN kabhi nahi maangenge.",
    "real_courier_delivery": "Hello, Delhivery se bol raha hoon, aapka parcel aaj shaam tak aayega. Ghar pe koi rahega?",
}


async def main():
    for name, text in CALLS.items():
        r = await evon_judge.judge(text)
        evon = f"{r['risk']:3} {r['scam_type']}" if r else "no answer"
        print(f"{name:28} rules={rules.score(text)['score']:3}  evon={evon}")


if __name__ == "__main__":
    asyncio.run(main())
