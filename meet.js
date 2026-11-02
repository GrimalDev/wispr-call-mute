// Executed inside Google Meet by Vivaldi's Apple Events interface.
// Only click an explicit microphone-off action. Never use a toggle shortcut.
function meetMicrophone(action, token = '') {
  const key = '__wisprCallMuteSession';
  const saved = window[key];
  if (action === 'restore' && (!token || !saved || saved.token !== token || saved.url !== location.href)) return 'untouched';
  const visible = e => e.getClientRects().length > 0;
  const controls = [...document.querySelectorAll('button,[role="button"]')].filter(visible);
  const label = e => (e.getAttribute('aria-label') || '').trim();
  const off = /^(Turn off microphone|Mute microphone|Désactiver le micro(?:phone)?|Couper le micro(?:phone)?)(?:\s|$|\()/i;
  const on = /^(Turn on microphone|Unmute microphone|Activer le micro(?:phone)?|Réactiver le micro(?:phone)?)(?:\s|$|\()/i;
  const candidates = controls.filter(e => off.test(label(e)) || on.test(label(e)));
  if (candidates.length !== 1) return 'unknown';
  const button = candidates[0];
  if (action === 'restore') {
    // Require the same control to still be mounted. Leaving/rejoining a call
    // replaces its controls, so restoration must not touch the new session.
    if (saved.button !== button) return 'untouched';
    if (off.test(label(button))) {
      delete window[key];
      return 'unmuted';
    }
    if (button.disabled || button.getAttribute('aria-disabled') === 'true') return 'unknown';
    button.click();
    return 'pending';
  }
  if (on.test(label(button))) return 'muted';
  if (action === 'inspect') return 'unmuted';
  if (button.disabled || button.getAttribute('aria-disabled') === 'true') return 'unknown';
  if (token) window[key] = {token, button, url: location.href};
  button.click();
  return 'pending';
}
