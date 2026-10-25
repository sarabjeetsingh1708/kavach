"""chunk -> transcript -> score -> warn -> alert. One CallSession per live call or uploaded file."""
import asyncio
import time

from . import alerts, config, evon_judge, gnani_stt, gnani_tts, rules

RETRIGGER_JUMP = 20  # ask Evon again right away when the rule score rises this much since its last look


def combine(rule_risk: int, evon_risk) -> int:
    """Blend the two layers so each vetoes the other's false alarms.
    Red needs one layer sure (>= ALERT) and the other at least suspicious (>= CAUTION); a disagreement is capped
    just below red, so the parent hears the soft "be careful" prompt. Without an Evon answer, rules decide alone.
    Found in testing: Evon alone scored a genuine police passport-verification call 95; rules alone scored a genuine
    bank call that said "we will never ask for your OTP" 100."""
    if evon_risk is None:
        return rule_risk
    hi, lo = max(rule_risk, evon_risk), min(rule_risk, evon_risk)
    if hi >= config.ALERT_THRESHOLD and lo < config.CAUTION_THRESHOLD:
        return config.ALERT_THRESHOLD - 1
    return hi


class CallSession:
    def __init__(self, use_evon: bool = True, send_alerts: bool = True):
        self.use_evon = use_evon and bool(config.EVON_URL)
        self.send_alerts = send_alerts
        self.transcript = ""
        self.risk = 0
        self.scam_type = "none"
        self.reasons: list = []
        self.advice_hi = ""
        self.alerted = False
        self.started = time.time()
        self.first_alert_s = None
        self._evon_task = None
        self._last_evon = 0.0
        self.rule_risk = 0
        self.evon_risk = None  # None until Evon has answered at least once
        self._rule_at_last_evon = 0

    def _update_risk(self):
        self.risk = max(self.risk, combine(self.rule_risk, self.evon_risk))  # only goes up during a call: no flicker

    def _apply_rules(self):
        res = rules.score(self.transcript)
        self.rule_risk = max(self.rule_risk, res["score"])
        if self.scam_type == "none":
            self.scam_type = res["scam_type"]
        for r in res["reasons"]:
            if r not in self.reasons:
                self.reasons.append(r)
        self._update_risk()

    async def _run_evon(self):
        self._last_evon = time.time()
        self._rule_at_last_evon = self.rule_risk
        res = await evon_judge.judge(self.transcript)
        if not res:
            return
        # latest whole-call judgement wins (Evon may calm down once it hears more, e.g. "we never ask for OTP")
        self.evon_risk = res["risk"]
        if res["scam_type"] != "none":
            self.scam_type = res["scam_type"]
        self.advice_hi = res["advice_hi"] or self.advice_hi
        self.reasons = list(dict.fromkeys(res["reasons"] + self.reasons))
        self._update_risk()

    def level(self) -> str:
        if self.risk >= config.ALERT_THRESHOLD:
            return "danger"
        if self.risk >= config.CAUTION_THRESHOLD:
            return "caution"
        return "safe"

    def state(self) -> dict:
        lvl = self.level()
        lang = gnani_tts.detect_language(self.transcript)  # warn in the language the call is in
        warning = gnani_tts.plain(gnani_tts.warning_for(lvl, self.scam_type, lang))
        return {
            "transcript": self.transcript,
            "risk": self.risk,
            "level": lvl,
            "scam_type": self.scam_type,
            "reasons": self.reasons[:6],
            "advice_hi": self.advice_hi,
            "language": lang,
            "warning_text": warning,
            "warning_audio": {"danger": f"/warning/{self.scam_type}?lang={lang}",
                              "caution": f"/warning/caution?lang={lang}"}.get(lvl),
            "seconds_to_alert": round(self.first_alert_s, 1) if self.first_alert_s is not None else None,
        }

    async def add_text(self, text: str, final: bool = False) -> dict:
        """Append transcript text and re-score the whole call. `fire_alert` is True exactly once, on first danger."""
        if text:
            self.transcript = f"{self.transcript} {text}".strip()
        self._apply_rules()
        if self.use_evon:
            if final:  # file mode: wait for the context judge; whole call known, so no monotonic lock-in
                await self._run_evon()
                self.risk = combine(self.rule_risk, self.evon_risk)
            elif (time.time() - self._last_evon >= config.EVON_INTERVAL_S
                  or self.rule_risk - self._rule_at_last_evon >= RETRIGGER_JUMP) and (
                    self._evon_task is None or self._evon_task.done()):
                self._evon_task = asyncio.create_task(self._run_evon())  # background: never blocks the warning
        st = self.state()
        st["fire_alert"] = False
        if st["level"] == "danger" and not self.alerted:
            self.alerted = True
            self.first_alert_s = time.time() - self.started
            st["seconds_to_alert"] = round(self.first_alert_s, 1)
            st["fire_alert"] = True
            if self.send_alerts:
                asyncio.create_task(alerts.alert_guardian(st))
        return st

    async def add_audio(self, audio: bytes, final: bool = False) -> dict:
        return await self.add_text(await gnani_stt.transcribe(audio), final=final)
