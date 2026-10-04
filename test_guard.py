from app import violations, plan, targets, workout, week, PROFILE
A = PROFILE["avoid"]
assert violations("Add crushed peanuts on top", A) == ["peanut"]
assert violations("pea\u200bnut sauce", A) == ["peanut"]                      # zero-width bypass
assert violations("\uff50\uff45\uff41\uff4e\uff55\uff54 butter", A) == ["peanut"]  # full-width
assert "prawn" in violations("Garlic prawns with rice", A)                    # second allergen
assert "nut" in violations("a handful of mixed nuts", A)
assert violations("Dal with rice, paneer and good nutrition", A) == []        # no false alarm
drafts = iter(["Almond curry", "Plain dal"])
r = plan("dinner", generate=lambda _: next(drafts)); assert r["ok"] and r["attempts"] == 2
r = plan("dinner", generate=lambda _: "cashew rice"); assert not r["ok"]
t = targets(PROFILE); assert 2700 < t["kcal"] < 3100 and t["protein_g"] > 100, t
# workout planner: whitelisted sessions, exercise guard, weekly split
assert workout("rm -rf", generate=lambda _: "x")["ok"] is False
assert sum(1 for d in week(PROFILE) if d["session"]) == PROFILE["gym_days"]
d = iter(["Behind the neck press 3x8", "Bench press 3x8"])
r = workout("Upper A", generate=lambda _: next(d)); assert r["ok"] and r["attempts"] == 2
print("all tests passed", t)
