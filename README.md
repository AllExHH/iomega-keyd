[English](README.en.md) | **Deutsch**

# iomega-keyd – Iomega ScreenPlay Fernbedienung unter CoreELEC/Kodi

Macht die Fernbedienung des **Iomega ScreenPlay TV Link DX** (Modell 35045, NEC-Protokoll,
Adresse `0x53`) unter **CoreELEC/Kodi** voll nutzbar – inklusive der QWERTY-Tastatur auf
der Rückseite und der Steuerscheibe als Mauszeiger.

Getestet mit CoreELEC 21 auf einem Odroid N2+ (Hardware-IR-Empfänger).

## Inhalt

| Datei | Zweck |
|---|---|
| `keymaps/iomega_screenplay.toml` | Keymap für `ir-keytable`: Navigation, Wiedergabe, Lautstärke, Ziffern |
| `iomega_keyd.py` | Dienst für die QWERTY-Tastatur (Fn/Alt/Symbol/Shift/Caps) und den Mausmodus |
| `iomega_keyd.json` | Konfiguration: angelernte Scancodes, Tastaturlayout, Maus |
| `autostart.sh` | Zeile für `/storage/.config/autostart.sh` |
| `keymaps/iomega_screenplay_dx.lircd.conf` | Gleiche Codes für LIRC |
| `keymaps/iomega_screenplay_dx.ir` | Gleiche Codes für den Flipper Zero (zum Testen/Nachsenden) |
| `tests/test_keyd.py` | Tests der Tastatur-Logik (ohne Hardware) |
| `tools/find_nec_codes.py` | Sucht NEC-Codetabellen in Firmware-Dateien |

## 1. Grundtasten (Keymap)

```bash
# auf der CoreELEC-Box (SSH)
mkdir -p /storage/.config/rc_keymaps
cp keymaps/iomega_screenplay.toml /storage/.config/rc_keymaps/
ir-keytable -c -w /storage/.config/rc_keymaps/iomega_screenplay.toml
ir-keytable -t        # Tasten drücken, Codes werden angezeigt (Strg+C beendet)
```

Dauerhaft laden: in `/storage/.config/rc_maps.cfg` die Zeile

```
* * iomega_screenplay.toml
```

eintragen und neu starten.

## 2. QWERTY-Tastatur (iomega-keyd)

Der Dienst bildet die Tastatur-Logik der Original-Firmware nach:

| Taste (Farbe) | Wirkung |
|---|---|
| **Fn** (orange) | nächste Taste = Akzentbuchstabe (à ą ã é …) |
| **Alt** (rot) | nächste Taste = Ziffer / rotes Zeichen |
| **Symbol** (blau) | nächste Taste = blaues Sonderzeichen |
| **Shift** | nächster Buchstabe groß |
| **Caps Lock** | Großschreibung an/aus |

Fn, Alt, Symbol und Shift drückt man **nacheinander**: erst die Sondertaste, dann die
Zeichentaste. Sie gelten nur für ein Zeichen. Sonderfälle: Fn+Space = æ, Fn+Symbol = ø,
Fn+Punkt = ö, Symbol+Punkt = Komma.

Der Dienst liest die Scancodes direkt vom IR-Gerät. Alles, was er nicht selbst braucht
(Pfeile, Play, Lautstärke …), reicht er unverändert weiter. Die Keymap aus Schritt 1
bleibt also in Gebrauch. Er braucht nur Python 3 und keine Zusatzpakete.

### Installation

1. Den Repo-Ordner per SMB/SSH nach `/storage/.config/iomega-keyd/` kopieren.
2. **Tasten anlernen** (Kodi darf laufen, der Dienst noch nicht):
   ```bash
   python3 /storage/.config/iomega-keyd/iomega_keyd.py --learn
   ```
   Jede angezeigte Taste einmal kurz drücken. 10 s ohne Druck überspringt die Taste.
   Das Ergebnis wird in `iomega_keyd.json` gespeichert.
3. In Kodi das Tastaturlayout prüfen (*Einstellungen → System → Eingabe →
   Tastaturlayout*) und in `iomega_keyd.json` unter `"layout"` gleich setzen
   (`"de"` oder `"us"`).
4. Testen:
   ```bash
   python3 /storage/.config/iomega-keyd/iomega_keyd.py
   ```
5. **Autostart:** Die Zeile aus `autostart.sh` in `/storage/.config/autostart.sh`
   übernehmen und neu starten. Log: `/storage/.kodi/temp/iomega_keyd.log`.

Nur Scancodes ansehen: `iomega_keyd.py --monitor`

### Mausmodus

Die linke Steuerscheibe sendet 16 Richtungen. Im Mausmodus wird sie zum Mauszeiger
(länger halten = schneller), OK ist der Klick. Zum Einschalten in `iomega_keyd.json` unter
`"mouse" → "toggle"` den Scancode einer Taste eintragen, die zwischen Maus und normaler
Bedienung umschalten soll. `"start_enabled": true` startet direkt im Mausmodus.

### Konfiguration (`iomega_keyd.json`)

| Schlüssel | Bedeutung |
|---|---|
| `layout` | `de` (QWERTZ) oder `us` – muss zu Kodi passen |
| `device` | IR-Gerät, z. B. `/dev/input/event3`; `null` = automatisch suchen |
| `repeat_window_ms` | Wiederholungen innerhalb dieser Zeit gelten als „gehalten“ |
| `fallback_strip_accents` | Zeichen, die das Layout nicht kennt, ohne Akzent tippen (à → a) |
| `letters` / `keys` / `modifiers` | Scancodes (werden von `--learn` gefüllt) |
| `mouse` | Mausmodus: `toggle`, `click`, `step`, `max_step`, `directions` |

## Hinweise

- Stehen beim Anlernen Codes, die in der toml schon als `KEY_1` … belegt sind, diese
  Zeilen aus der toml entfernen. Sonst sind sie doppelt belegt. Der Dienst fängt das
  zwar ab, ohne Doppelbelegung ist es aber sauberer.
- Im Layout `de` fehlen ` und ^ (Tottasten).
- Fehlermeldung „Gerät ist belegt“: Der Dienst läuft schon (`killall python3` bzw.
  Autostart prüfen).

## Tests

```bash
python3 tests/test_keyd.py
```

## Quellen

Die Codes und die Tastatur-Logik stammen aus der Original-Firmware des ScreenPlay DX
(`libosdengine.a`, `input_dfb_events.o`, `irkernel.c.patch`) aus
[coolshou/screenplay-dx](https://github.com/coolshou/screenplay-dx). Dieses Repo enthält
keine Firmware-Dateien.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
