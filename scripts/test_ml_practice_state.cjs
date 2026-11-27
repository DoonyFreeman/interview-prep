const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');

const context = {};
runInNewContext(readFileSync(join(__dirname, 'templates/ml-practice-state.js'), 'utf8'), context);
const create = context.MLPracticeStore.create;
const key = 'practice';
function memory() {
  const entries = new Map();
  return {
    entries,
    getItem(name) { return entries.has(name) ? entries.get(name) : null; },
    setItem(name, value) { entries.set(name, value); },
  };
}

test('a stale tab closing without edits cannot overwrite newer notes', () => {
  const storage = memory();
  const a = create(storage, key, ['01', '02']);
  const b = create(storage, key, ['01', '02']);
  a.update('01', 'notes', 'Новый расчёт');
  a.save();
  b.save();
  b.update('02', 'done', true);
  b.save();
  const reopened = create(storage, key, ['01', '02']);
  assert.equal(reopened.state['01'].notes, 'Новый расчёт');
  assert.equal(reopened.state['02'].done, true);
});

test('independent fields of the same task cannot replace each other', () => {
  const storage = memory();
  const a = create(storage, key, ['01']);
  const b = create(storage, key, ['01']);
  a.update('01', 'notes', 'TP=4');
  b.update('01', 'done', true);
  b.save();
  a.save();
  const reopened = create(storage, key, ['01']);
  assert.equal(reopened.state['01'].notes, 'TP=4');
  assert.equal(reopened.state['01'].done, true);
});

test('storage events update untouched fields and preserve unsaved input', () => {
  const a = create(memory(), key, ['01']);
  a.update('01', 'notes', 'Пишу решение');
  a.receive('practice:01:notes', JSON.stringify('Старая запись'));
  a.receive('practice:01:done', 'true');
  assert.equal(a.state['01'].notes, 'Пишу решение');
  assert.equal(a.state['01'].done, true);
  a.receive('practice:01:done', '{bad');
  assert.equal(a.state['01'].done, true);
  a.receive(null, null);
  assert.equal(a.state['01'].done, false);
  assert.equal(a.state['01'].notes, 'Пишу решение');
});

test('quota failures leave input usable and dirty fields retryable', () => {
  const storage = memory();
  const a = create(storage, key, ['01']);
  a.update('01', 'notes', 'Не потерять');
  const write = storage.setItem;
  storage.setItem = () => { throw new Error('Quota exceeded'); };
  assert.equal(a.save(), false);
  assert.equal(a.available, false);
  assert.equal(a.state['01'].notes, 'Не потерять');
  storage.setItem = write;
  assert.equal(a.save(), true);
  assert.equal(create(storage, key, ['01']).state['01'].notes, 'Не потерять');
});

test('legacy snapshots migrate on edits, including empty notes and false marks', () => {
  const storage = memory();
  storage.setItem(key, JSON.stringify({ '01': { notes: 'До обновления', done: true } }));
  const a = create(storage, key, ['01']);
  assert.equal(a.state['01'].notes, 'До обновления');
  a.update('01', 'notes', '');
  a.update('01', 'done', false);
  a.save();
  const reopened = create(storage, key, ['01']);
  assert.equal(reopened.state['01'].notes, '');
  assert.equal(reopened.state['01'].done, false);
});

test('unavailable storage and invalid updates cannot break the exercise state', () => {
  const a = create(null, key, ['01']);
  a.update('01', 'notes', 'Можно решать без сохранения');
  assert.equal(a.save(), false);
  assert.equal(a.state['01'].notes, 'Можно решать без сохранения');
  assert.throws(() => a.update('__proto__', 'notes', 'bad'));
  assert.throws(() => a.update('01', 'done', 'true'));
});
