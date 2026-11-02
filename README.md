# Wispr call mute

Hold **Option/Alt + T** to mute your calls and dictate with Wispr Flow. Release **T** to stop dictation and restore each call's previous mute state. Already-muted calls stay muted.

Works with **Tuple** and **Google Meet in Vivaldi** on macOS. Karabiner handles the physical key; Flow starts and stops through its native URL commands. No simulated keystrokes or SKHD required.

## Install

Requires Python 3.9+, [Karabiner-Elements](https://karabiner-elements.pqrs.org/), Wispr Flow, and Vivaldi. Tuple users need a version with its bundled CLI.

```sh
git clone https://github.com/GrimalDev/wispr-call-mute.git
cd wispr-call-mute
python3 install.py
```

1. Open Karabiner-Elements at least once before installing. The installer adds a rule to its selected profile and backs up its configuration.
2. For Meet, enable **Vivaldi → Settings → Privacy → Apple Events → Allow JavaScript from Apple Events**. Allow the Karabiner worker to control Vivaldi if macOS asks. This browser permission also allows scripts on other sites.
3. Keep Flow running and signed in. Focus a text field, hold **Option-T**, wait for Flow's recording indicator, and speak. Release **T** to finish.

Keep the cloned folder in place. Re-run the installer if you move it. No changes to Flow's own shortcuts are needed.

## Uninstall

```sh
python3 install.py --remove
```

Removes this rule from the selected Karabiner profile. Other shortcuts and Flow settings stay unchanged.

## Notes

- Wait for the previous transcription to finish before starting another. A short press released before muting completes starts no dictation.
- Covers current calls only. Calls joined or manually unmuted during dictation are not monitored.
- Meet controls support English and French. Unknown controls block dictation. Meet's live-call behavior needs broader testing; Tuple and native Flow start/stop have been tested locally.
- Flow's URL commands and active-session marker are undocumented and may change. If the stop command fails, calls stay muted.
- Direct Flow shortcuts and mouse activation bypass this automation. Release **T**, not just Option, to stop.

Read-only diagnostic: `python3 mute_flow.py`. Runtime logs: `.runtime/bridge.log`.

Tests: `python3 -m unittest discover` and `node test_meet.js` (Node.js is only needed for the JavaScript tests).
