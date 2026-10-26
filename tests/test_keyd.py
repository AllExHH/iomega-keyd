import os, sys, json, importlib.util
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) < 3:
    sys.argv[1:] = [os.path.join(_ROOT, "iomega_keyd.py"), os.path.join(_ROOT, "iomega_keyd.json")]
spec = importlib.util.spec_from_file_location("kd", sys.argv[1]); kd = importlib.util.module_from_spec(spec); spec.loader.exec_module(kd)
cfg = json.load(open(sys.argv[2]))
# Fake-Scancodes fuer Tests
for i, c in enumerate("qwertyuiopasdfghjklzxcvbnm"): cfg["letters"][c] = "0x%04x" % (0x9000 + i)
cfg["keys"] = {"space": "0x9100", "dot": "0x9101", "backspace": "0x9102"}
cfg["modifiers"] = {"fn": "0x5378", "shift": "0x9201", "alt": "0x9202", "symbol": "0x9203", "caps": "0x9204"}
cfg["mouse"]["toggle"] = "0x9300"
L = {c: 0x9000 + i for i, c in enumerate("qwertyuiopasdfghjklzxcvbnm")}
SH, AL, SY, CP, FN, SP, DT, BS = 0x9201, 0x9202, 0x9203, 0x9204, 0x5378, 0x9100, 0x9101, 0x9102
tr = kd.Translator(cfg); t = [0.0]
def press(*scs):
    out = []
    for sc in scs:
        t[0] += 1.0
        c, a = tr.on_scan(sc, t[0]); out += [x[1] for x in a if x[0] == "text"]
    return "".join(out)
ok = True
def check(name, got, exp):
    global ok; r = got == exp; ok &= r
    print(("OK  " if r else "FAIL"), name, repr(got), "" if r else "erwartet %r" % exp)
check("klein", press(L["h"], L["a"], L["l"], L["l"], L["o"]), "hallo")
check("Shift einmalig", press(SH, L["h"], L["i"]), "Hi")
check("Caps an/aus", press(CP, L["a"], L["b"], CP, L["c"]), "ABc")
check("Alt Ziffern", press(AL, L["q"], AL, L["p"]), "10")
check("Alt leer (a)", press(AL, L["a"], L["a"]), "a")
check("Symbol", press(SY, L["w"], SY, L["k"]), "@/")
check("Fn Akzent", press(FN, L["a"], FN, L["n"]), "àñ")
check("Fn+Caps", press(CP, FN, L["e"], CP), "Ã")
check("Fn+Space", press(FN, SP), "æ")
check("Fn+Symbol", press(FN, SY), "ø")
check("Punkt/Komma/ö", press(DT, SY, DT, FN, DT), ".,ö")
check("Modifier ersetzt", press(FN, SH, L["a"]), "A")
# Wiederholung (Halten) tippt nicht doppelt
t[0] += 1; c1, a1 = tr.on_scan(L["x"], t[0]); c2, a2 = tr.on_scan(L["x"], t[0] + 0.11)
check("Halten = 1x", [x[1] for x in a1 + a2], ["x"])
# Fremde Taste wird durchgereicht
c, a = tr.on_scan(0x5301, 100.0); check("Pfeil hoch durchreichen", (c, a), (False, []))
# Maus
tr.on_scan(0x9300, 200.0); c, a = tr.on_scan(0x5344, 201.0); check("Maus hoch", (c, a[0][0], a[0][1], a[0][2] < 0), (True, "move", 0, True))
c, a = tr.on_scan(0x5340, 202.0); check("Maus Klick", a, [("click",)])
tr.on_scan(0x9300, 203.0); c, a = tr.on_scan(0x5344, 204.0); check("Maus aus -> Play durch", c, False)
# Layout-Abdeckung
for lay in ("de", "us"):
    m = kd.LAYOUTS[lay](); miss = set()
    for tab in (kd.SYM, kd.ALT):
        for ch in tab.values():
            if ch not in m and not kd.fallback(ch): miss.add(ch)
    for ch in list(kd.FN_LOWER.values()) + list(kd.FN_UPPER.values()) + ["æ", "ø", "ö", "Ö"]:
        if ch not in m and not (kd.fallback(ch) and all(c in m for c in kd.fallback(ch))): miss.add(ch)
    print("Layout", lay, "nicht tippbar:", "".join(sorted(miss)) or "-")
print("ALLE OK" if ok else "FEHLER")
sys.exit(0 if ok else 1)
