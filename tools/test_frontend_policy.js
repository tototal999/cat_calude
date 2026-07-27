const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const calls = {
  listDocuments: 0,
  latestWorkflow: 0,
  listModels: 0,
  documentAction: null
};
const elements = new Map();
let copiedText = null;

function element(tagName = 'div') {
  return {
    tagName: tagName.toUpperCase(),
    style: {},
    children: [],
    classList: { add() {}, remove() {} },
    appendChild(child) { this.children.push(child); return child; },
    querySelector() { return element('p'); }
  };
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
  createElement(tagName) { return element(tagName); }
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
    },
    list_models() {
      calls.listModels += 1;
      return Promise.resolve(['company-fast', 'company-quality']);
    },
    current_model() {
      return Promise.resolve('company-quality');
    },
    open_document_dialog() {
      return Promise.resolve('deck.pptx');
    },
    ingest_document() {
      return Promise.resolve({
        document: { id: 'deck-id', name: 'deck.pptx', suffix: '.pptx' }
      });
    },
    document_action(documentId, action) {
      calls.documentAction = { documentId, action };
      return Promise.resolve({ answer: 'Complete summary', sources: [] });
    }
  } },
  navigator: { clipboard: {
    writeText(value) {
      copiedText = value;
      return Promise.resolve();
    }
  } },
  setInterval,
  clearInterval,
  alert() {}
};

vm.createContext(context);
vm.runInContext(fs.readFileSync('frontend/chat.js', 'utf8'), context);
const indexHtml = fs.readFileSync('frontend/index.html', 'utf8');

async function run() {
  assert.match(
    indexHtml,
    /onclick="runDocumentAction\('summary'\)">快速摘要（抽樣）<\/button>/);
  assert.match(
    indexHtml,
    /onclick="runDocumentAction\('full_summary'\)">完整分析（全部投影片）<\/button>/);

  context.applyFeaturePolicy({ documents: true, 'documents.meeting_pack': false });
  context.showTab('documents');
  await new Promise(resolve => setImmediate(resolve));
  assert.strictEqual(calls.listModels, 1, 'opening documents must load company models');
  assert.deepStrictEqual(
    elements.get('model-select').children.map(option => option.value),
    ['company-fast', 'company-quality']);

  context.applyFeaturePolicy({ documents: false, 'documents.meeting_pack': false });
  context.showTab('documents');
  assert.strictEqual(calls.listDocuments, 1);
  assert.strictEqual(calls.latestWorkflow, 0);

  context.applyFeaturePolicy({ documents: true, 'documents.meeting_pack': true });
  context.showTab('documents');
  assert.strictEqual(calls.listDocuments, 2);
  assert.strictEqual(calls.latestWorkflow, 1);

  context.chooseDocument();
  await new Promise(resolve => setImmediate(resolve));
  context.runDocumentAction('full_summary');
  assert.match(
    document.getElementById('document-answer').textContent,
    /全部投影片/);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepStrictEqual(calls.documentAction, {
    documentId: 'deck-id',
    action: 'full_summary'
  });

  const answer = document.getElementById('document-answer');
  answer.children = [];
  context.renderDocumentResult({
    answer: '付款期限為 30 天。',
    coverage: {
      included_chunks: 22,
      total_chunks: 22,
      complete: true,
      limited_chunks: 1
    },
    sources: [{ source: { document_name: '採購流程.pdf', locator: '第 8 頁' }, excerpt: '來源文字' }]
  });
  const copyButton = answer.children.find(child => child.tagName === 'BUTTON');
  assert.ok(copyButton, 'document result must include a copy button');
  const coverage = answer.children.find(
    child => child.className === 'document-coverage-note');
  assert.ok(coverage, 'complete analysis must show its coverage');
  assert.match(coverage.textContent, /22\/22/);
  assert.match(coverage.textContent, /1/);
  copyButton.onclick();
  await new Promise(resolve => setImmediate(resolve));
  assert.strictEqual(copiedText, '付款期限為 30 天。');

  console.log('frontend policy routing: PASS');
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
