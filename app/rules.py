"""Layer 1: instant keyword/phrase red-flag scorer (Hindi in Devanagari, Hinglish, English, plus basic
Tamil and Bengali keywords). No API calls.

Prisma returns Hindi in Devanagari ("अरेस्ट वारंट"), while typed demos and English calls are in Latin script,
so every rule matches both. Text is normalized first (nukta and zero-width chars removed, spaces collapsed).

Scam calls pair a PRETEXT (police, bank, parcel, relative, prize) with an ASK (OTP, money, app, secrecy).
Either alone is common in normal calls; together they are the strongest signal, so the pair earns a bonus."""
import re
import unicodedata

ASK, PRETEXT, PRESSURE = "ask", "pretext", "pressure"

# (regex, points, kind, scam_type or None, human-readable reason). Avoid \b next to Devanagari (matras break it).
RULES = [
    # asks: what the scammer wants from you
    (r"\botp\b|ओ ?टी ?पी|one time password|code (that appears|bata)|कोड बता|ஓ ?டி ?பி|ও ?টি ?পি", 25, ASK, None,
     "Asks for an OTP / code"),
    (r"\bupi pin\b|\bpin\b|\bcvv\b|expiry date|पिन|सीवीवी|सी वी वी|एक्सपायरी डेट", 22, ASK, None,
     "Asks for a PIN/CVV/card details"),
    (r"anydesk|teamviewer|quick ?support|screen ?share|\bapk\b|app install|एनी ?डेस्क|टीम ?व्यूअर|स्क्रीन ?शेयर"
     r"|ऐप (इंस्टॉल|डाउनलोड)|एप (इंस्टॉल|डाउनलोड)|इंस्टॉल कर", 30, ASK, None, "Asks to install an app / share screen"),
    (r"paise (bhej|transfer|jama)|(bhej|transfer kar) do|\btransfer\b|send (the |it|money)|\bpay\b|payment kar"
     r"|fine (bhar|abhi|pay)|\bfine\b|hazaar|clearance amount"
     r"|पैसे (भेज|ट्रांसफर|जमा)|ट्रांसफर|पेमेंट|फाइन|जुर्माना|हजार|रुपये भेज|भेज (दो|दीजिए|दें)|[0-9][0-9,]{3,}"
     r"|(चार्ज|पैसे|रुपये?) (पे|भर|जमा) कर"
     r"|பணம்|ட்ரான்ஸ்ஃபர்|டிரான்ஸ்பர்|ட்ரான்ஸ்பர்|கட்ட|টাকা|ট্রান্সফার|পাঠান", 22, ASK, None,
     "Asks you to send money"),
    (r"link (pe|par) click|click (on )?(the )?link|link (bhej|we sent)|is link|लिंक|क्लिक|லிங்க்|கிளிக்|লিংক|ক্লিক",
     18, ASK, None,
     "Asks to click a link"),
    (r"safe account|rbi account|verification account|secure account|fd tod"
     r"|सेफ अकाउंट|आरबीआई अकाउंट|आर बी आई|वेरिफिकेशन अकाउंट|एफडी तोड़|एफ डी तोड", 30, ASK, None,
     "Asks to move money to a 'safe account'"),
    (r"processing fee|registration fee|(tax|gst|charges?) (bhej|pay|jama|katta)|claim fee|fee (bhej|katta)"
     r"|प्रोसेसिंग फीस|रजिस्ट्रेशन फीस|(टैक्स|जीएसटी|जी एस टी|चार्ज) (भेज|जमा|भर)|फीस (भेज|जमा|भर)", 28, ASK,
     "lottery", "Asks a fee to release a prize/refund"),
    # pressure: secrecy and urgency
    (r"kisi (ko|se) (bhi )?mat|kisi ko na bata|(mummy|papa|ghar mein kisi|family) ko (bhi )?(mat|nahi)"
     r"|don'?t tell|yaarukkum sollaadh|confidential"
     r"|किसी (को|से) (भी )?(मत|ना|न )|(मम्मी|पापा|घर में किसी|फैमिली|परिवार) को (भी )?(मत|नहीं)|कॉन्फिडेंशियल|गुप्त"
     r"|யாருக்கும் சொல்ல|কাউকে বলবেন না",
     25, PRESSURE, None, "Tells you to keep it secret"),
    (r"abhi ke abhi|turant|jaldi|immediately|right now|urgent|aaj (hi|raat)|sirf aaj"
     r"|अभी के अभी|तुरंत|जल्दी|अर्जेंट|आज (ही|रात)|सिर्फ आज|अभी", 12, PRESSURE, None, "Creates urgency"),
    # pretexts: who the scammer pretends to be
    (r"\bcbi\b|\bncb\b|narcotics control|\bed officer\b|cyber ?crime|police|judge"
     r"|सी ?बी ?आई|एन ?सी ?बी|पुलिस|साइबर ?क्राइम|जज|ईडी ऑफिसर|इंस्पेक्टर|ऑफिसर"
     r"|சி ?பி ?ஐ|போலீஸ்|ஆஃபிசர்|অফিসার|পুলিশ|সি ?বি ?আই", 18, PRETEXT,
     "digital_arrest", "Claims to be police/CBI/officials"),
    (r"arrest|giraftar|warrant|गिरफ्तार|अरेस्ट|वारंट|அரெஸ்ட்|வாரண்ட்|গ্রেফতার|অ্যারেস্ট", 28, PRETEXT, "digital_arrest", "Threatens arrest"),
    (r"video call|camera (on|chalu)|skype|nigrani|do not disconnect|वीडियो कॉल|कैमरा (ऑन|चालू)|स्काइप|निगरानी",
     15, PRETEXT, "digital_arrest", "Demands to stay on video call"),
    (r"aapke naam (pe|par)|money laundering|hawala|\bfir\b|case (darj|register|irukku)|registered against"
     r"|आपके नाम (पे|पर)|मनी ?लॉन्ड्रिंग|हवाला|एफ ?आई ?आर|केस (दर्ज|रजिस्टर)|கேஸ் இருக்கு|মামলা", 18, PRETEXT,
     "digital_arrest",
     "Claims a case is registered in your name"),
    (r"\bkyc\b|के ?वाई ?सी|கே ?ஒய் ?சி|কে ?ওয়াই ?সি", 22, PRETEXT, "kyc_bank", "Mentions KYC update"),
    (r"(account|card|khata).{0,20}(band|block|freeze|suspend)|card .{0,10}expire"
     r"|(अकाउंट|खाता|कार्ड).{0,20}(बंद|ब्लॉक|फ्रीज|सस्पेंड)|कार्ड .{0,10}एक्सपायर"
     r"|(அக்கவுண்ட்|அக்கவுன்ட்).{0,20}(ப்ளாக்|மூட)|(অ্যাকাউন্ট|একাউন্ট).{0,20}(বন্ধ|ব্লক)", 28, PRETEXT, "kyc_bank",
     "Threatens to block account/card"),
    (r"\bbank\b|\bsbi\b|hdfc|icici|pan card|aadhaa?r|credit card|debit card"
     r"|बैंक|एसबीआई|एस बी आई|एचडीएफसी|आईसीआईसीआई|पैन ?कार्ड|आधार|क्रेडिट कार्ड|डेबिट कार्ड|பேங்க்|வங்கி|ব্যাঙ্ক|ব্যাংক",
     8, PRETEXT, "kyc_bank",
     "Claims to be from a bank / mentions IDs"),
    (r"courier|parcel|fedex|\bdhl\b|customs|india post|कूरियर|कुरियर|पार्सल|फेडेक्स|डीएचएल|कस्टम्स|कस्टम",
     12, PRETEXT, "courier", "Mentions a parcel/courier"),
    (r"drugs|narcotics|fake passport|illegal (items|goods|saman)|seized|pakda"
     r"|ड्रग्स|नशीले|फर्जी पासपोर्ट|फेक पासपोर्ट|अवैध|गैरकानूनी|पकड़ा|पकडा", 28, PRETEXT, "courier",
     "Claims illegal items / seizure"),
    (r"\bpapa\b|\bmummy\b|\bmom\b|\bdad\b|\bmaa\b|\bbeta\b|bhaiya|mama ji|chacha|aunty"
     r"|पापा|मम्मी|बेटा|भैया|मामा जी|चाचा|आंटी", 4, PRETEXT, "fake_relative", "Claims to be a relative/acquaintance"),
    (r"accident|police ne pakad|pakad liya|emergency|operation ke liye|hospital ka bill"
     r"|एक्सीडेंट|ऐक्सिडेंट|दुर्घटना|पकड लिया|[इए]मरजेंसी|ऑपरेशन के लिए|हॉस्पिटल का बिल", 18, PRETEXT,
     "fake_relative", "Claims an emergency"),
    (r"naya number|naye number|number badal|phone (kharab|toot)|new number|phone broke"
     r"|नया नंबर|नए नंबर|नंबर बदल|फोन (खराब|टूट)", 18, PRETEXT, "fake_relative", "Says 'this is my new number'"),
    (r"lottery|lucky draw|jeet[aei]|jackpot|\bprize\b|inaam|congratulations|won (a|rs)"
     r"|लॉटरी|लकी ड्रा|जीत[ाेी]|जैकपॉट|प्राइज|इनाम|बधाई हो|லாட்டரி|பிரைஸ்|பரிசு|লটারি|পুরস্কার", 28, PRETEXT, "lottery", "Claims you won a prize"),
    (r"refund|cashback|रिफंड|कैशबैक", 10, PRETEXT, "lottery", "Promises a refund/cashback"),
]
PAIR_BONUS = 25  # pretext + ask in the same call
# Below this many distinct red flags the score is capped under the caution line (cuts false alarms).
MIN_FLAGS = 2
SINGLE_FLAG_CAP = 35


def normalize(text: str) -> str:
    """Unify spelling variants Prisma produces: drop nukta (फ़ -> फ), half nasal -> anusvara
    (ट्रान्सफर -> ट्रांसफर), zero-width chars, extra spaces. Applied to both patterns and transcripts."""
    text = unicodedata.normalize("NFD", text).replace("़", "")
    text = re.sub(r"[​-‍]", "", text)
    text = re.sub(r"[नमणङञ]्(?=[क-ह])", "ं", unicodedata.normalize("NFC", text))
    return re.sub(r"\s+", " ", text)


_COMPILED = [(re.compile(normalize(p), re.I), pts, kind, t, why) for p, pts, kind, t, why in RULES]


def score(transcript: str) -> dict:
    """Returns {score 0-100, scam_type, reasons, hits}. Each rule counts at most once."""
    transcript = normalize(transcript)
    total = 0
    by_type: dict = {}
    kinds: set = set()
    reasons: list = []
    for rx, pts, kind, scam_type, why in _COMPILED:
        if rx.search(transcript):
            total += pts
            kinds.add(kind)
            reasons.append(why)
            if scam_type:
                by_type[scam_type] = by_type.get(scam_type, 0) + pts
    if PRETEXT in kinds and ASK in kinds:
        total += PAIR_BONUS
    scam_type = max(by_type, key=by_type.get) if by_type else "none"
    if len(reasons) < MIN_FLAGS:
        total = min(total, SINGLE_FLAG_CAP)
    return {"score": min(total, 100), "scam_type": scam_type, "reasons": reasons, "hits": len(reasons)}
