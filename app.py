#!/usr/bin/env python3
"""SafePlate: a local gym-meal planner for one person. Gemma writes, plain code checks."""
import json, re, unicodedata, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = "gemma3:1b"
PROFILE = json.load(open("profile.json", encoding="utf-8"))
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)


def normalise(text):
    """NFKC + strip zero-width chars so hidden spellings can't sneak past."""
    return unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH).lower()


def violations(text, avoid):
    """Return the avoided ingredients found in text. No model involved."""
    t = normalise(text)
    return [a for a in avoid if re.search(rf"\b{re.escape(normalise(a))}s?\b", t)]


def targets(p):
    """Daily calorie and protein targets from the Mifflin-St Jeor formula. Estimates only."""
    bmr = 10 * p["weight_kg"] + 6.25 * p["height_cm"] - 5 * p["age"] + (5 if p["sex"] == "male" else -161)
    factor = {"light": 1.375, "moderate": 1.55, "high": 1.725}[p["activity"]]
    adjust = {"cut": -400, "maintain": 0, "gain": 300}[p["goal"]]
    protein_per_kg = {"cut": 2.0, "maintain": 1.6, "gain": 1.8}[p["goal"]]
    return {"kcal": int(round(bmr * factor + adjust, -1)),
            "protein_g": int(round(p["weight_kg"] * protein_per_kg)), "goal": p["goal"]}


def prompt(request):
    p, t = PROFILE, targets(PROFILE)
    return (
        f"You are a practical meal planner for {p['name']}, who goes to the gym. Diet: {p['diet']}. "
        f"Goal: {t['goal']} weight. Daily target: about {t['kcal']} kcal and {t['protein_g']} g protein. "
        f"Likes: {', '.join(p['likes'])}. Notes: {p['notes']}\n"
        f"Request: {request}\n"
        "Write in a plain, neutral tone and start directly with the first meal. "
        "For each meal give: name, ingredients, 2-3 quick steps, and approximate calories and protein in grams."
    )


def ask_ollama(text):
    body = json.dumps({"model": MODEL, "prompt": text, "stream": False,
                       "options": {"temperature": 0.4}}).encode()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["response"]


def guarded(text, avoid, generate, tries=3):
    """Generate, check with plain code, retry. The model never gets the last word."""
    bad = []
    for attempt in range(1, tries + 1):
        out = generate(text)
        bad = violations(out, avoid)
        if not bad:
            return {"ok": True, "plan": out, "attempts": attempt}
    return {"ok": False, "plan": "Could not produce a safe result. Try again or rephrase.",
            "attempts": tries, "blocked": bad}


def plan(request, generate=ask_ollama):
    return guarded(prompt(request), PROFILE["avoid"], generate)


# The weekly split is fixed in code, so the model only fills in one session at a time.
SPLITS = {2: ["Full body A", "Full body B"], 3: ["Full body A", "Full body B", "Full body C"],
          4: ["Upper A", "Lower A", "Upper B", "Lower B"],
          5: ["Push", "Pull", "Legs", "Upper", "Lower"],
          6: ["Push A", "Pull A", "Legs A", "Push B", "Pull B", "Legs B"]}
SLOTS = {2: [0, 3], 3: [0, 2, 4], 4: [0, 1, 3, 4], 5: [0, 1, 2, 4, 5], 6: [0, 1, 2, 3, 4, 5]}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GOALS = {"cut": "fat loss", "maintain": "general fitness", "gain": "muscle gain"}


def week(p):
    slots = dict(zip(SLOTS[p["gym_days"]], SPLITS[p["gym_days"]]))
    return [{"day": d, "session": slots.get(i)} for i, d in enumerate(WEEKDAYS)]


def workout_prompt(session):
    p = PROFILE
    return (f"You are a practical gym coach. Write a '{session}' session for a {p['experience']} lifter "
            f"with access to: {p['equipment']}. Goal: {GOALS[p['goal']]}. "
            "Start directly with a 5 minute warm-up, then 5 to 6 exercises. "
            "For each exercise give sets x reps and rest time. Plain, neutral tone, no extra commentary.")


def workout(session, generate=ask_ollama):
    if session not in SPLITS[PROFILE["gym_days"]]:
        return {"ok": False, "plan": "Unknown session.", "attempts": 0}
    return guarded(workout_prompt(session), PROFILE.get("avoid_exercises", []), generate)


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers()
        self.wfile.write(body.encode())

    def _host_ok(self):  # refuse anything not addressed to localhost
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._host_ok(): return self._send(403, "no", "text/plain")
        html = open("page.html", encoding="utf-8").read()
        html = (html.replace("__AVOID_JSON__", json.dumps(PROFILE["avoid"]))
                    .replace("__TARGETS_JSON__", json.dumps(targets(PROFILE)))
                    .replace("__WEEK_JSON__", json.dumps(week(PROFILE)))
                    .replace("__NAME_JSON__", json.dumps(PROFILE["name"])))
        self._send(200, html, "text/html")

    def do_POST(self):
        if not self._host_ok(): return self._send(403, "no", "text/plain")
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/workout":
            result = workout(str(data.get("session", ""))[:40])
        elif self.path == "/plan":
            result = plan(str(data.get("request", ""))[:500])
        else:
            return self._send(404, "no", "text/plain")
        self._send(200, json.dumps(result), "application/json")


if __name__ == "__main__":
    print("SafePlate on http://127.0.0.1:8000")
    HTTPServer(("127.0.0.1", 8000), H).serve_forever()
