ObjC.import('Foundation');
function isMeetingUrl(url) {
  // Meet uses both /abc-defg-hij and /meet/abc-defg-hij for room URLs.
  return /^https:\/\/meet\.google\.com\/(?:(?:meet\/)?[a-z]{3}-[a-z]{4}-[a-z]{3}|lookup\/[^/?#]+|new)(?:[/?#]|$)/i.test(url);
}
function run(args) {
  const action = args[0] || 'inspect';
  if (!['inspect', 'mute', 'restore'].includes(action)) throw Error('Invalid action');
  const token = args[2] || '';
  const source = ObjC.unwrap($.NSString.stringWithContentsOfFileEncodingError(args[1], $.NSUTF8StringEncoding, null));
  if (!source) throw Error('Cannot read Meet adapter');
  const app = Application('Vivaldi');
  if (!app.running()) return JSON.stringify({running: false, meetings: []});
  const meetings = [];
  for (const window of app.windows()) {
    for (const tab of window.tabs()) {
      const url = tab.url();
      // Skip the Meet homepage; include meeting rooms and lookup links.
      if (!isMeetingUrl(url)) continue;
      const execute = mode => tab.execute({javascript: source + '\nmeetMicrophone(' + JSON.stringify(mode) + ',' + JSON.stringify(token) + ')'});
      let state = execute(action);
      if (state === 'pending') {
        const desired = action === 'restore' ? 'unmuted' : 'muted';
        for (let i = 0; i < 12 && state !== desired; i++) {
          delay(0.1);
          state = execute('inspect');
        }
        if (action === 'restore' && state === desired) execute('restore');
      }
      // Do not log meeting URLs, participants, or page content.
      meetings.push({state});
    }
  }
  return JSON.stringify({running: true, meetings});
}
