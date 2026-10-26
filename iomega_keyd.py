#!/usr/bin/env python3
"""
iomega_keyd - QWERTY-Tastatur der Iomega-ScreenPlay-Fernbedienung unter CoreELEC/Kodi.

Bildet das Verhalten der Original-Firmware nach (aus dmaosd ausgelesen):
  - Fn / Shift / Alt / Symbol gelten fuer genau EINE folgende Taste,
    danach ist der Modifier wieder aus. Caps Lock schaltet dauerhaft um.
  - Fn (orange)   -> Akzentbuchstaben (a -> à ...), mit Caps Lock gross
  - Alt (rot)     -> Ziffern und rote Zeichen
  - Symbol (blau) -> blaue Sonderzeichen
  - Fn + Space -> æ, Fn + Symbol -> ø, Fn + Punkt -> ö, Symbol + Punkt -> ,
  - Optional: Steuerscheibe als 16-Wege-Mauszeiger (wie im Original-Browser).

Liest die Scancodes direkt vom IR-Eingabegeraet (EV_MSC/MSC_SCAN), daher muessen
Buchstaben NICHT in der ir-keytable-Keymap stehen. Alle anderen Tasten werden
unveraendert an Kodi weitergereicht. Benoetigt nur Python 3, keine Zusatzpakete.

Aufruf:
  iomega_keyd.py            Dienst starten
  iomega_keyd.py --learn    Tasten nacheinander druecken und Scancodes speichern
  iomega_keyd.py --monitor  Scancodes nur anzeigen (wie ir-keytable -t)
"""

import fcntl
import glob
import json
import os
import select
import signal
import struct
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "iomega_keyd.json")

# ---------------------------------------------------------------- Linux-Input
EV_SYN, EV_KEY, EV_REL, EV_MSC = 0, 1, 2, 4
SYN_REPORT, MSC_SCAN = 0, 4
REL_X, REL_Y = 0, 1
BTN_LEFT = 0x110
KEY_MAX = 0x2FF

EVENT_FMT = "@llHHi"                      # struct input_event (32/64 Bit passend)
EVENT_SIZE = struct.calcsize(EVENT_FMT)

EVIOCGRAB = 0x40044590
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502

K = {  # benoetigte Keycodes (linux/input-event-codes.h)
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "MINUS": 12, "EQUAL": 13, "BACKSPACE": 14, "ENTER": 28,
    "q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21, "u": 22, "i": 23, "o": 24, "p": 25,
    "LEFTBRACE": 26, "RIGHTBRACE": 27,
    "a": 30, "s": 31, "d": 32, "f": 33, "g": 34, "h": 35, "j": 36, "k": 37, "l": 38,
    "SEMICOLON": 39, "APOSTROPHE": 40, "GRAVE": 41, "LEFTSHIFT": 42, "BACKSLASH": 43,
    "z": 44, "x": 45, "c": 46, "v": 47, "b": 48, "n": 49, "m": 50,
    "COMMA": 51, "DOT": 52, "SLASH": 53, "SPACE": 57, "102ND": 86, "RIGHTALT": 100,
}
LETTERS = "abcdefghijklmnopqrstuvwxyz"

# ------------------------------------------------- Zeichentabellen (Firmware)
FN_LOWER = dict(zip(LETTERS, "àßçśãşèğìïłõńñóòåéäęüćążùź"))
FN_UPPER = dict(zip(LETTERS, "ÀßÇŚÃŞÈĞÌÏŁÕŃÑÓÒÅÉÄĘÜĆĄŻÙŹ"))
ALT = {"e": "3", "g": "_", "i": "8", "j": "|", "k": "\\", "l": ":", "o": "9", "p": "0",
       "q": "1", "r": "4", "t": "5", "u": "7", "w": "2", "y": "6"}
SYM = dict(zip(LETTERS, "`<{'#\"-+*=/;?>()!$~%&}@]^["))

# ---------------------------------------------- Tastaturlayouts fuer Kodi
# Zeichen -> (Keycode, Shift, AltGr). Muss zum in Kodi eingestellten Layout passen.
def _layout_us():
    m = {}
    for ch in LETTERS:
        m[ch] = (K[ch], False, False)
        m[ch.upper()] = (K[ch], True, False)
    for i, ch in enumerate("1234567890"):
        m[ch] = (K[ch], False, False)
        m["!@#$%^&*()"[i]] = (K[ch], True, False)
    for base, sh, key in [("-", "_", "MINUS"), ("=", "+", "EQUAL"), ("[", "{", "LEFTBRACE"),
                          ("]", "}", "RIGHTBRACE"), ("\\", "|", "BACKSLASH"),
                          (";", ":", "SEMICOLON"), ("'", '"', "APOSTROPHE"),
                          ("`", "~", "GRAVE"), (",", "<", "COMMA"), (".", ">", "DOT"),
                          ("/", "?", "SLASH")]:
        m[base] = (K[key], False, False)
        m[sh] = (K[key], True, False)
    m[" "] = (K["SPACE"], False, False)
    return m


def _layout_de():
    m = {}
    for ch in LETTERS:
        key = {"y": "z", "z": "y"}.get(ch, ch)          # QWERTZ
        m[ch] = (K[key], False, False)
        m[ch.upper()] = (K[key], True, False)
    for i, ch in enumerate("1234567890"):
        m[ch] = (K[ch], False, False)
        m['!"§$%&/()='[i]] = (K[ch], True, False)
    rows = [  # (Taste, normal, Shift, AltGr)
        ("MINUS", "ß", "?", "\\"), ("RIGHTBRACE", "+", "*", "~"),
        ("LEFTBRACE", "ü", "Ü", None), ("SEMICOLON", "ö", "Ö", None),
        ("APOSTROPHE", "ä", "Ä", None), ("BACKSLASH", "#", "'", None),
        ("102ND", "<", ">", "|"), ("COMMA", ",", ";", None), ("DOT", ".", ":", None),
        ("SLASH", "-", "_", None),
    ]
    for key, n, s, ag in rows:
        m[n] = (K[key], False, False)
        m[s] = (K[key], True, False)
        if ag:
            m[ag] = (K[key], False, True)
    for ch, key in [("@", "q"), ("{", "7"), ("[", "8"), ("]", "9"), ("}", "0"), ("€", "e")]:
        m[ch] = (K[key], False, True)
    m[" "] = (K["SPACE"], False, False)
    # ` und ^ sind im deutschen Layout Tottasten -> nicht zuverlaessig, fehlen bewusst
    return m


LAYOUTS = {"us": _layout_us, "de": _layout_de}

# Fuer Zeichen, die das Layout nicht kennt (z.B. à im US-Layout)
FALLBACK_EXTRA = {"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE",
                  "ß": "ss", "ı": "i"}


def fallback(ch):
    if ch in FALLBACK_EXTRA:
        return FALLBACK_EXTRA[ch]
    base = "".join(c for c in unicodedata.normalize("NFD", ch)
                   if unicodedata.category(c) != "Mn")
    return base if base and base != ch else None


# ------------------------------------------------------------------ Config
def parse_sc(v):
    if v is None or v == "":
        return None
    return int(v, 16) if isinstance(v, str) else int(v)


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# -------------------------------------------------------------- Uebersetzer
FN, ALTM, SYMM, SHIFT = "fn", "alt", "symbol", "shift"


class Translator:
    """Zustandsmaschine wie in der Original-Firmware. Gibt Aktionen zurueck:
    ('text', str) | ('key', code) | ('move', dx, dy) | ('click',)"""

    def __init__(self, cfg):
        self.repeat_window = cfg.get("repeat_window_ms", 200) / 1000.0
        self.letters = {}
        for ch, sc in cfg.get("letters", {}).items():
            sc = parse_sc(sc)
            if sc is not None:
                self.letters[sc] = ch.lower()
        keys = cfg.get("keys", {})
        self.sc_space = parse_sc(keys.get("space"))
        self.sc_dot = parse_sc(keys.get("dot"))
        self.sc_backspace = parse_sc(keys.get("backspace"))
        self.mods = {}
        for name, sc in cfg.get("modifiers", {}).items():
            sc = parse_sc(sc)
            if sc is not None:
                self.mods[sc] = name
        mouse = cfg.get("mouse", {})
        self.sc_mouse_toggle = parse_sc(mouse.get("toggle"))
        self.sc_mouse_click = parse_sc(mouse.get("click"))
        self.step = mouse.get("step", 6)
        self.max_step = mouse.get("max_step", 40)
        self.dirs = {}
        for sc, vec in mouse.get("directions", {}).items():
            dx, dy = vec
            n = (dx * dx + dy * dy) ** 0.5 or 1
            self.dirs[parse_sc(sc)] = (dx / n, dy / n)
        self.oneshot = None      # fn | alt | symbol | shift
        self.caps = False
        self.mouse_on = bool(mouse.get("start_enabled", False))
        self.last_sc, self.last_t, self.hold_start = None, 0.0, 0.0

    def _char_for_letter(self, l):
        if self.oneshot == FN:
            return (FN_UPPER if self.caps else FN_LOWER)[l]
        if self.oneshot == ALTM:
            return ALT.get(l)                      # leer = keine Ausgabe (wie Original)
        if self.oneshot == SYMM:
            return SYM[l]
        if self.oneshot == SHIFT or self.caps:
            return l.upper()
        return l

    def on_scan(self, sc, now):
        """-> (verbraucht: bool, aktionen: list)"""
        repeat = sc == self.last_sc and (now - self.last_t) < self.repeat_window
        if not repeat:
            self.hold_start = now
        self.last_sc, self.last_t = sc, now

        if self.sc_mouse_toggle is not None and sc == self.sc_mouse_toggle:
            if not repeat:
                self.mouse_on = not self.mouse_on
                log("Mausmodus %s" % ("AN" if self.mouse_on else "AUS"))
            return True, []
        if self.mouse_on:
            if sc in self.dirs:
                held = now - self.hold_start
                speed = min(self.max_step, self.step * (1 + 2.5 * held))
                dx, dy = self.dirs[sc]
                return True, [("move", round(dx * speed), round(dy * speed))]
            if sc == self.sc_mouse_click:
                return True, ([] if repeat else [("click",)])

        if sc in self.mods:
            if repeat:
                return True, []
            name = self.mods[sc]
            if name == "caps":
                self.caps = not self.caps
                return True, []
            if name == SYMM and self.oneshot == FN:        # Fn + Symbol -> ø
                self.oneshot = None
                return True, [("text", "Ø" if self.caps else "ø")]
            self.oneshot = name                             # ersetzt andere Modifier
            return True, []

        if sc == self.sc_backspace:
            return True, [("key", K["BACKSPACE"])]          # Halten = mehrfach loeschen

        if sc in self.letters or sc in (self.sc_space, self.sc_dot):
            if repeat:
                return True, []
            if sc == self.sc_space:
                ch = ("Æ" if self.caps else "æ") if self.oneshot == FN else " "
            elif sc == self.sc_dot:
                if self.oneshot == FN:
                    ch = "Ö" if self.caps else "ö"
                elif self.oneshot == SYMM:
                    ch = ","
                else:
                    ch = "."
            else:
                ch = self._char_for_letter(self.letters[sc])
            self.oneshot = None
            return True, ([("text", ch)] if ch else [])

        return False, []


# ------------------------------------------------------------------ Ausgabe
class UInput:
    def __init__(self, name, keys=(), rels=()):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        if keys:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            for k in keys:
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, k)
        if rels:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
            for r in rels:
                fcntl.ioctl(self.fd, UI_SET_RELBIT, r)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_SYN)
        dev = struct.pack("80sHHHHi", name.encode()[:79], 0x06, 0x1d6b, 0x0153, 1, 0)
        dev += b"\0" * (4 * 64 * 4)
        os.write(self.fd, dev)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        time.sleep(0.3)

    def emit(self, etype, code, value):
        os.write(self.fd, struct.pack(EVENT_FMT, 0, 0, etype, code, value))

    def syn(self):
        self.emit(EV_SYN, SYN_REPORT, 0)

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)


class Output:
    def __init__(self, cfg):
        self.layout = LAYOUTS[cfg.get("layout", "de")]()
        self.use_fallback = cfg.get("fallback_strip_accents", True)
        self.kbd = UInput("iomega-keyd keyboard", keys=range(1, KEY_MAX + 1))
        self.mouse = UInput("iomega-keyd mouse", keys=(BTN_LEFT, BTN_LEFT + 1),
                            rels=(REL_X, REL_Y))

    def forward_key(self, code, value):
        self.kbd.emit(EV_KEY, code, value)
        self.kbd.syn()

    def tap(self, code, shift=False, altgr=False):
        mods = ([K["LEFTSHIFT"]] if shift else []) + ([K["RIGHTALT"]] if altgr else [])
        for m in mods:
            self.kbd.emit(EV_KEY, m, 1)
        self.kbd.emit(EV_KEY, code, 1)
        self.kbd.syn()
        self.kbd.emit(EV_KEY, code, 0)
        for m in reversed(mods):
            self.kbd.emit(EV_KEY, m, 0)
        self.kbd.syn()

    def text(self, s):
        for ch in s:
            spec = self.layout.get(ch)
            if spec is None and self.use_fallback:
                fb = fallback(ch)
                if fb:
                    self.text(fb)
                    continue
            if spec is None:
                log("Zeichen %r im Layout nicht verfuegbar - uebersprungen" % ch)
                continue
            self.tap(*spec)

    def move(self, dx, dy):
        self.mouse.emit(EV_REL, REL_X, dx)
        self.mouse.emit(EV_REL, REL_Y, dy)
        self.mouse.syn()

    def click(self):
        self.mouse.emit(EV_KEY, BTN_LEFT, 1)
        self.mouse.syn()
        self.mouse.emit(EV_KEY, BTN_LEFT, 0)
        self.mouse.syn()

    def run(self, action):
        kind = action[0]
        if kind == "text":
            self.text(action[1])
        elif kind == "key":
            self.tap(action[1])
        elif kind == "move":
            self.move(action[1], action[2])
        elif kind == "click":
            self.click()

    def close(self):
        self.kbd.close()
        self.mouse.close()


# ------------------------------------------------------------------ Eingabe
def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def find_rc_device(cfg):
    if cfg.get("device"):
        return cfg["device"]
    for path in sorted(glob.glob("/sys/class/rc/rc*/input*/event*")):
        return "/dev/input/" + os.path.basename(path)
    return None


def open_rc(cfg, grab=True, wait=True):
    while True:
        dev = find_rc_device(cfg)
        if dev and os.path.exists(dev):
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            if grab:
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, 1)
                except OSError:
                    os.close(fd)
                    sys.exit("Geraet %s ist belegt - laeuft iomega_keyd schon? "
                             "(killall python3 bzw. Autostart pruefen)" % dev)
            log("IR-Geraet: %s" % dev)
            return fd
        if not wait:
            sys.exit("Kein IR-Eingabegeraet unter /sys/class/rc gefunden.")
        time.sleep(2)


def read_frames(fd):
    """Liefert pro SYN_REPORT eine Liste von (type, code, value)."""
    frame = []
    while True:
        select.select([fd], [], [])
        try:
            data = os.read(fd, EVENT_SIZE * 64)
        except BlockingIOError:
            continue
        for off in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
            _, _, t, c, v = struct.unpack_from(EVENT_FMT, data, off)
            if t == EV_SYN and c == SYN_REPORT:
                yield frame
                frame = []
            else:
                frame.append((t, c, v))


# ------------------------------------------------------------------- Modi
def run_daemon(cfg):
    tr = Translator(cfg)
    out = Output(cfg)
    fd = open_rc(cfg)
    suppressed = set()   # Keycodes, deren Druck verbraucht wurde (Loslassen auch schlucken)

    def stop(*_):
        try:
            fcntl.ioctl(fd, EVIOCGRAB, 0)
        except OSError:
            pass
        out.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log("laeuft (Layout %s, %d Buchstaben konfiguriert)"
        % (cfg.get("layout", "de"), len(tr.letters)))

    for frame in read_frames(fd):
        scans = [v & 0xFFFFFFFF for t, c, v in frame if t == EV_MSC and c == MSC_SCAN]
        consumed, actions = (False, [])
        if scans:
            consumed, actions = tr.on_scan(scans[-1], time.monotonic())
        for t, c, v in frame:
            if t != EV_KEY:
                continue
            if consumed and v in (1, 2):
                suppressed.add(c)
            elif c in suppressed:
                if v == 0:
                    suppressed.discard(c)
            else:
                out.forward_key(c, v)
        for a in actions:
            out.run(a)


def run_monitor(cfg):
    fd = open_rc(cfg, grab=False, wait=False)
    log("Tasten druecken, Strg+C beendet.")
    for frame in read_frames(fd):
        for t, c, v in frame:
            if t == EV_MSC and c == MSC_SCAN:
                print("scancode 0x%04x" % (v & 0xFFFFFFFF), flush=True)


LEARN_ORDER = (list("qwertyuiopasdfghjklzxcvbnm")
               + ["dot", "backspace", "space", "fn", "shift", "alt", "symbol", "caps"])


def run_learn(cfg):
    fd = open_rc(cfg, grab=True, wait=False)
    print("Jede Taste EINMAL kurz druecken (ohne Fn/Shift davor).")
    print("10 s ohne Druck = Taste ueberspringen. Strg+C = abbrechen und speichern.\n")
    found = {}
    last_sc, last_t = None, 0.0
    try:
        for name in LEARN_ORDER:
            label = name.upper() if len(name) == 1 else name
            print("Druecke: %-10s" % label, end=" ", flush=True)
            deadline = time.monotonic() + 10
            got = None
            while got is None and time.monotonic() < deadline:
                r, _, _ = select.select([fd], [], [], 0.2)
                if not r:
                    continue
                data = os.read(fd, EVENT_SIZE * 64)
                for off in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                    _, _, t, c, v = struct.unpack_from(EVENT_FMT, data, off)
                    if t != EV_MSC or c != MSC_SCAN:
                        continue
                    sc, now = v & 0xFFFFFFFF, time.monotonic()
                    fresh = not (sc == last_sc and now - last_t < 0.6)
                    last_sc, last_t = sc, now
                    if fresh and got is None:
                        got = sc
            if got is None:
                print("-> uebersprungen")
                continue
            dup = [k for k, v in found.items() if v == got]
            found[name] = got
            print("-> 0x%04x%s" % (got, ("   ACHTUNG: gleich wie " + dup[0]) if dup else ""))
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nabgebrochen")
    finally:
        fcntl.ioctl(fd, EVIOCGRAB, 0)

    for name, sc in found.items():
        hx = "0x%04x" % sc
        if len(name) == 1:
            cfg.setdefault("letters", {})[name] = hx
        elif name in ("dot", "backspace", "space"):
            cfg.setdefault("keys", {})[name] = hx
        else:
            cfg.setdefault("modifiers", {})[name] = hx
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print("\nGespeichert in %s (%d Tasten)." % (CONFIG_PATH, len(found)))


def main():
    cfg = load_config()
    if "--learn" in sys.argv:
        run_learn(cfg)
    elif "--monitor" in sys.argv:
        run_monitor(cfg)
    else:
        run_daemon(cfg)


if __name__ == "__main__":
    main()
