const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/meet.js', 'utf8');
function test(labels, action, expected, clicksExpected, disabled = false) {
  let clicks = 0;
  const elements = labels.map(label => ({
    getClientRects: () => [1],
    getAttribute: name => name === 'aria-label' ? label : null,
    click: () => clicks++, disabled
  }));
  const context = {window: {}, location: {href: 'https://meet.google.com/aaa-bbbb-ccc'}, document: {querySelectorAll: () => elements}};
  const actual = vm.runInNewContext(source + `\nmeetMicrophone(${JSON.stringify(action)})`, context);
  assert.equal(actual, expected);
  assert.equal(clicks, clicksExpected);
}
test(['Turn off microphone (⌘ + d)'], 'mute', 'pending', 1);
test(['Turn on microphone (⌘ + d)'], 'mute', 'muted', 0);
test(['Turn off microphone'], 'inspect', 'unmuted', 0);
test(['Désactiver le micro (⌘ + d)'], 'mute', 'pending', 1);
test(['Activer le micro'], 'mute', 'muted', 0);
test(['Turn off camera'], 'mute', 'unknown', 0);
test(['Turn off microphone', 'Turn on microphone'], 'mute', 'unknown', 0);
test(['Turn off microphone'], 'mute', 'unknown', 0, true);
let muted = false;
let clicks = 0;
const button = {
  getClientRects: () => [1],
  getAttribute: name => name === 'aria-label' ? (muted ? 'Turn on microphone' : 'Turn off microphone') : null,
  click: () => {muted = !muted; clicks++;}
};
const context = vm.createContext({window: {}, location: {href: 'https://meet.google.com/aaa-bbbb-ccc'}, document: {querySelectorAll: () => [button]}});
vm.runInContext(source, context);
const run = (action, token) => vm.runInContext(`meetMicrophone(${JSON.stringify(action)}, ${JSON.stringify(token)})`, context);
assert.equal(run('mute', 'one'), 'pending');
assert.equal(muted, true);
assert.equal(run('restore', 'other'), 'untouched');
assert.equal(muted, true);
assert.equal(run('restore', 'one'), 'pending');
assert.equal(muted, false);
assert.equal(run('restore', 'one'), 'unmuted');
assert.equal(clicks, 2);
muted = true;
assert.equal(run('mute', 'two'), 'muted');
assert.equal(run('restore', 'two'), 'untouched');
assert.equal(muted, true);
muted = false;
run('mute', 'three');
context.location.href = 'https://meet.google.com/ddd-eeee-fff';
assert.equal(run('restore', 'three'), 'untouched');
assert.equal(muted, true);
console.log('Meet mute and restoration checks passed');

// Exercise the actual Vivaldi tab enumeration, including Meet's /meet/ prefix.
const executed = [];
const roomUrls = [
  'https://meet.google.com/aaa-bbbb-ccc',
  'https://meet.google.com/meet/aaa-bbbb-ccc',
  'https://meet.google.com/meet/aaa-bbbb-ccc?authuser=1',
  'https://meet.google.com/lookup/example',
  'https://meet.google.com/new',
];
const skippedUrls = [
  'https://meet.google.com/',
  'https://meet.google.com/landing',
  'https://meet.google.com/meet/',
  'https://meet.google.com/meet/aaa-bbbb-ccc-extra',
  'https://meet.google.com.evil.test/meet/aaa-bbbb-ccc',
  'https://example.com/meet/aaa-bbbb-ccc',
];
const adapterContext = vm.createContext({
  ObjC: {import: () => {}, unwrap: value => value},
  $: {NSString: {stringWithContentsOfFileEncodingError: () => source}},
  Application: () => ({
    running: () => true,
    windows: () => [{tabs: () => [...roomUrls, ...skippedUrls].map(url => ({
      url: () => url,
      execute: () => {executed.push(url); return 'muted';},
    }))}],
  }),
});
vm.runInContext(fs.readFileSync(__dirname + '/vivaldi.js', 'utf8'), adapterContext);
const result = JSON.parse(vm.runInContext("run(['inspect', 'meet.js'])", adapterContext));
assert.deepEqual(executed, roomUrls);
assert.equal(result.meetings.length, roomUrls.length);
assert.ok(result.meetings.every(meeting => meeting.state === 'muted'));
console.log('Vivaldi Meet URL routing checks passed');
