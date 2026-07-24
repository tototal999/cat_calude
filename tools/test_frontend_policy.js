const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const calls = { listDocuments: 0, latestWorkflow: 0 };
const elements = new Map();

function element() {
  return { style: {}, classList: { add() {}, remove() {} } };
}

const document = {
  body: { style: {} },
  getElementById(id) {
    if (id === 'sidebar-resize') return null;
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  },
  querySelectorAll() { return []; },
  addEventListener() {},
  createElement() { return element(); }
};

const context = {
  console,
  document,
  window: { addEventListener() {} },
  pywebview: { api: {
    list_documents() {
      calls.listDocuments += 1;
      return { then() { return this; } };
    },
    latest_workflow_run() {
      calls.latestWorkflow += 1;
      return { then() { return this; } };
    }
  } },
  setInterval,
  clearInterval,
  alert() {}
};

vm.createContext(context);
vm.runInContext(fs.readFileSync('frontend/chat.js', 'utf8'), context);

context.applyFeaturePolicy({ documents: true, 'documents.meeting_pack': false });
context.showTab('documents');
assert.deepStrictEqual(calls, { listDocuments: 1, latestWorkflow: 0 });

context.applyFeaturePolicy({ documents: false, 'documents.meeting_pack': false });
context.showTab('documents');
assert.deepStrictEqual(calls, { listDocuments: 1, latestWorkflow: 0 });

context.applyFeaturePolicy({ documents: true, 'documents.meeting_pack': true });
context.showTab('documents');
assert.deepStrictEqual(calls, { listDocuments: 2, latestWorkflow: 1 });

console.log('frontend policy routing: PASS');
