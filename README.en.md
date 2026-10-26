**English** | [Deutsch](README.md)

# iomega-keyd – Iomega ScreenPlay remote control on CoreELEC/Kodi

Makes the remote control of the **Iomega ScreenPlay TV Link DX** (model 35045, NEC
protocol, address `0x53`) fully usable on **CoreELEC/Kodi**, including the QWERTY keyboard
on the back and the control disc as a mouse pointer.

Tested with CoreELEC 21 on an Odroid N2+ (hardware IR receiver).

## Contents

| File | Purpose |
|---|---|
| `keymaps/iomega_screenplay.toml` | Keymap for `ir-keytable`: navigation, playback, volume, digits |
| `iomega_keyd.py` | Service for the QWERTY keyboard (Fn/Alt/Symbol/Shift/Caps) and mouse mode |
| `iomega_keyd.json` | Configuration: learned scancodes, keyboard layout, mouse |
| `autostart.sh` | Line for `/storage/.config/autostart.sh` |
| `keymaps/iomega_screenplay_dx.lircd.conf` | Same codes for LIRC |
| `keymaps/iomega_screenplay_dx.ir` | Same codes for the Flipper Zero (for testing/replaying) |
| `tests/test_keyd.py` | Tests for the keyboard logic (no hardware needed) |
| `tools/find_nec_codes.py` | Searches firmware files for NEC code tables |

## 1. Basic keys (keymap)

```bash
# on the CoreELEC box (SSH)
mkdir -p /storage/.config/rc_keymaps
cp keymaps/iomega_screenplay.toml /storage/.config/rc_keymaps/
ir-keytable -c -w /storage/.config/rc_keymaps/iomega_screenplay.toml
ir-keytable -t        # press keys, codes are shown (Ctrl+C to quit)
```

To load it permanently, add this line to `/storage/.config/rc_maps.cfg`:

```
* * iomega_screenplay.toml
```

and reboot.

## 2. QWERTY keyboard (iomega-keyd)

The service reproduces the keyboard logic of the original firmware:

| Key (color) | Effect |
|---|---|
| **Fn** (orange) | next key = accented letter (à ą ã é …) |
| **Alt** (red) | next key = digit / red character |
| **Symbol** (blue) | next key = blue special character |
| **Shift** | next letter uppercase |
| **Caps Lock** | uppercase on/off |

Fn, Alt, Symbol and Shift are pressed **one after the other**: first the modifier key,
then the character key. They apply to one character only. Special cases:
Fn+Space = æ, Fn+Symbol = ø, Fn+Dot = ö, Symbol+Dot = comma.

The service reads scancodes directly from the IR device. Everything it doesn't need
itself (arrows, play, volume …) is passed through to Kodi unchanged, so the keymap from
step 1 stays in use. It only needs Python 3, no extra packages.

### Installation

1. Copy the repo folder to `/storage/.config/iomega-keyd/` via SMB/SSH.
2. **Learn the keys** (Kodi may be running, the service not yet):
   ```bash
   python3 /storage/.config/iomega-keyd/iomega_keyd.py --learn
   ```
   Press each key shown once, briefly. 10 s without a press skips the key.
   The result is saved to `iomega_keyd.json`.
3. Check the keyboard layout in Kodi (*Settings → System → Input → Keyboard layout*)
   and set the same value under `"layout"` in `iomega_keyd.json` (`"de"` or `"us"`).
4. Test:
   ```bash
   python3 /storage/.config/iomega-keyd/iomega_keyd.py
   ```
5. **Autostart:** add the line from `autostart.sh` to `/storage/.config/autostart.sh`
   and reboot. Log: `/storage/.kodi/temp/iomega_keyd.log`.

Show scancodes only: `iomega_keyd.py --monitor`

### Mouse mode

The left control disc sends 16 directions. In mouse mode it moves a mouse pointer
(hold longer = faster) and OK clicks. To enable it, put the scancode of a key that should
toggle between mouse and normal control under `"mouse" → "toggle"` in `iomega_keyd.json`.
`"start_enabled": true` starts directly in mouse mode.

### Configuration (`iomega_keyd.json`)

| Key | Meaning |
|---|---|
| `layout` | `de` (QWERTZ) or `us` – must match Kodi |
| `device` | IR device, e.g. `/dev/input/event3`; `null` = find automatically |
| `repeat_window_ms` | repeats within this time count as "held" |
| `fallback_strip_accents` | type characters the layout doesn't know without accent (à → a) |
| `letters` / `keys` / `modifiers` | scancodes (filled in by `--learn`) |
| `mouse` | mouse mode: `toggle`, `click`, `step`, `max_step`, `directions` |

## Notes

- If learning finds codes that are already mapped as `KEY_1` … in the toml, remove those
  lines from the toml. Otherwise they are mapped twice. The service handles that, but it
  is cleaner without the duplicates.
- The `de` layout lacks ` and ^ (dead keys).
- Error "device is busy": the service is already running (`killall python3` or check
  the autostart).

## Tests

```bash
python3 tests/test_keyd.py
```

## Sources

The codes and keyboard logic were taken from the original ScreenPlay DX firmware
(`libosdengine.a`, `input_dfb_events.o`, `irkernel.c.patch`) in
[coolshou/screenplay-dx](https://github.com/coolshou/screenplay-dx). This repo contains
no firmware files.

## License

MIT, see [LICENSE](LICENSE).
