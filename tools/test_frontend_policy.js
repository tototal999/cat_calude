const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const calls = {
  listDocuments: 0,
  latestWorkflow: 0,
  listModels: 0,
  documentAction: null,
  latestAnalysis: null
};
const elements = new Map();
const documentListeners = new Map();
let copiedText = null;

function element(tagName = 'div') {
  return {
    tagName: tagName.toUpperCase(),
    style: {},
    children: [],
    classList: { add() {}, remove() {} },
    appendChild(child) { this.children.push(child); return child; },
    insertBefore(child, reference) {
      const at = reference ? this.children.indexOf(reference) : 0;
      this.children.splice(at < 0 ? 0 : at, 0, child);
      return child;
    },
    get firstChild() { return this.children[0] || null; },
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
  addEventListener(name, handler) { documentListeners.set(name, handler); },
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
        document: { id: 'deck-id', name: 'deck.pptx', suffix: '.pptx' },
        reused: true
      });
    },
    latest_document_analysis(documentId) {
      calls.latestAnalysis = documentId;
      return Promise.resolve({
        kind: 'summary', label: '快速摘要（抽樣）', saved_at: '2026-07-28T10:16:14',
        answer: 'Saved summary', sources: [], coverage: {}
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
    /onclick="runDocumentAction\('full_summary'\)">完整分析（不抽樣）<\/button>/);

  // Drag-and-drop must stay cancelled: an unhandled drop navigates the window
  // to file:/// and request_open() never reloads the page, so the UI would be
  // stuck until a restart. The label must not invite the gesture either.
  assert.doesNotMatch(indexHtml, /拖文件給我/, 'the picker button must not promise drag and drop');
  for (const name of ['dragover', 'drop']) {
    const handler = documentListeners.get(name);
    assert.ok(handler, `chat.js must cancel ${name}`);
    let prevented = false;
    handler({ preventDefault() { prevented = true; } });
    assert.ok(prevented, `${name} must call preventDefault`);
  }
  assert.strictEqual(
    elements.get('document-status').textContent,
    '這個視窗不支援拖放，請按「選擇文件」。');

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
  await new Promise(resolve => setImmediate(resolve));
  // Re-picking an already indexed file must restore its saved analysis rather
  // than showing an empty pane - the bug that made results look lost.
  assert.strictEqual(calls.latestAnalysis, 'deck-id');
  assert.match(document.getElementById('document-status').textContent, /沿用既有結果/);
  const restored = document.getElementById('document-answer')
    .children.map(child => child.textContent || '').join('\n');
  assert.match(restored, /上次的「快速摘要（抽樣）」/);

  context.runDocumentAction('full_summary');
  assert.match(
    document.getElementById('document-answer').textContent,
    /全部內容/);
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
