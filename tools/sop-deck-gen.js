// ClaudeCat 使用者 SOP（投影版）
// 來源：claude-cat/使用者SOP_投影版大綱.md
// 主題：get-ppt 科技紫藍
const pptxgen = require("pptxgenjs");
const fs = require("fs");
// 簡報內容由同一份政策檔驅動，避免簡報教到已關閉的功能。
const path = require("path");
const POLICY_PATH = path.join(__dirname, "..", "feature-policy.json");
const F = JSON.parse(fs.readFileSync(POLICY_PATH, "utf8")).features || {};
const on = id => F[id] !== false;
console.log("政策：關閉 =", Object.keys(F).filter(k => !F[k]).join(", ") || "(無)");


const PALETTES = {
  violet: { primary: "5B4FE8", primaryLt: "8E86F5", navy: "0D0E2B", cardBg: "F0F2FA", codeBg: "15132E", codeText: "C9C5F5" },
};
const PALETTE = "violet";
const T = {
  ...PALETTES[PALETTE],
  violet: PALETTES[PALETTE].primary,
  alertRed: "D92D20", white: "FFFFFF", ink: "1E1F35", muted: "6B6E85",
  cardLine: "DDE1F2",
  fontCJK: "Microsoft JhengHei",
  fontCode: "Consolas",
};

const p = new pptxgen();
p.defineLayout({ name: "WIDE", width: 13.33, height: 7.5 });
p.layout = "WIDE";
const W = 13.33, H = 7.5, M = 0.6;

/* ---------- 版式 ---------- */
function frame(slide, title) {
  slide.background = { color: T.white };
  slide.addShape(p.ShapeType.rect, { x: 0, y: 0, w: W, h: 1.05, fill: { color: T.violet }, line: { type: "none" } });
  slide.addShape(p.ShapeType.rect, { x: 0, y: 1.05, w: 0.16, h: H - 1.05, fill: { color: T.violet }, line: { type: "none" } });
  slide.addText(title, { x: M, y: 0.12, w: W - 2 * M, h: 0.8, fontFace: T.fontCJK, fontSize: 28, bold: true, color: T.white, valign: "middle", margin: 0 });
}
function lead(slide, text, y = 1.3) {
  slide.addText(text, { x: M + 0.35, y, w: W - 2 * M - 0.5, h: 0.5, fontFace: T.fontCJK, fontSize: 19, bold: true, color: T.violet, valign: "middle", margin: 0 });
  return y + 0.62;
}
function badge(slide, x, y, n, d = 0.46) {
  slide.addShape(p.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: T.violet }, line: { type: "none" } });
  slide.addText(String(n), { x, y, w: d, h: d, fontFace: T.fontCJK, fontSize: 17, bold: true, color: T.white, align: "center", valign: "middle", margin: 0 });
}
// 淺色卡片（左側紫藍邊條）
function card(slide, { x, y, w, h, title, lines, titleSize = 18, bodySize = 14 }) {
  slide.addShape(p.ShapeType.rect, { x, y, w, h, fill: { color: T.cardBg }, line: { color: T.cardLine, width: 0.75 } });
  slide.addShape(p.ShapeType.rect, { x, y, w: 0.075, h, fill: { color: T.violet }, line: { type: "none" } });
  slide.addText(title, { x: x + 0.28, y: y + 0.16, w: w - 0.5, h: 0.4, fontFace: T.fontCJK, fontSize: titleSize, bold: true, color: T.violet, valign: "middle", margin: 0 });
  if (lines && lines.length) {
    slide.addText(lines.map((t) => ({ text: t, options: { bullet: { code: "2022" }, breakLine: true } })),
      { x: x + 0.28, y: y + 0.62, w: w - 0.5, h: h - 0.78, fontFace: T.fontCJK, fontSize: bodySize, color: T.ink, lineSpacingMultiple: 1.22, margin: 0, valign: "top" });
  }
}
// 依政策過濾後，把卡片排成 2x2 格線（自動塞滿，不留洞）
function cardGrid(slide, items, { y0 = 1.9, h = 2.25, gapY = 2.45 } = {}) {
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    card(slide, { x: M + 0.35 + col * 5.9, y: y0 + row * gapY, w: 5.6, h, ...it });
  });
}
// 編號步驟列
function steps(slide, items, { x = M + 0.35, y = 2.0, w = 11.6, gap = 0.78, size = 16 } = {}) {
  items.forEach((t, i) => {
    const yy = y + i * gap;
    badge(slide, x, yy, i + 1);
    slide.addText(t, { x: x + 0.68, y: yy - 0.06, w: w - 0.75, h: 0.6, fontFace: T.fontCJK, fontSize: size, color: T.ink, valign: "middle", margin: 0 });
  });
  return y + items.length * gap;
}
// 底部提醒條
function note(slide, text, y = 6.55, color) {
  slide.addShape(p.ShapeType.rect, { x: M + 0.35, y, w: W - 2 * M - 0.5, h: 0.55, fill: { color: "EEF0FA" }, line: { type: "none" } });
  slide.addText(text, { x: M + 0.55, y, w: W - 2 * M - 0.9, h: 0.55, fontFace: T.fontCJK, fontSize: 13.5, color: color || T.muted, valign: "middle", margin: 0 });
}
function cover(slide, o) {
  slide.background = { color: T.navy };
  slide.addShape(p.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: H, fill: { color: T.violet }, line: { type: "none" } });
  slide.addShape(p.ShapeType.rect, { x: 1.1, y: 2.05, w: 0.85, h: 0.14, fill: { color: T.violet }, line: { type: "none" } });
  slide.addText(o.kicker, { x: 1.1, y: 2.4, w: 10, h: 0.5, fontFace: T.fontCJK, fontSize: 16, color: "B7B8CE", margin: 0 });
  slide.addText([
    { text: o.titleTop, options: { breakLine: true, color: T.white } },
    { text: o.titleBottom, options: { color: T.primaryLt } },
  ], { x: 1.1, y: 3.0, w: 11.5, h: 1.9, fontFace: T.fontCJK, fontSize: 46, bold: true, lineSpacingMultiple: 1.06, margin: 0 });
  slide.addText(o.subtitle, { x: 1.1, y: 5.05, w: 11.5, h: 0.5, fontFace: T.fontCJK, fontSize: 17, color: "AAABCB", margin: 0 });
  slide.addText(o.date, { x: 1.1, y: 5.75, w: 8, h: 0.4, fontFace: T.fontCJK, fontSize: 14, color: T.primaryLt, bold: true, margin: 0 });
}
function closing(slide, o) {
  slide.background = { color: T.navy };
  slide.addShape(p.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: H, fill: { color: T.violet }, line: { type: "none" } });
  slide.addText(o.kicker, { x: M, y: 2.2, w: W - 2 * M, h: 0.5, fontFace: T.fontCJK, fontSize: 16, color: "9A9CB5", align: "center", margin: 0 });
  slide.addText(o.headline, { x: M, y: 2.8, w: W - 2 * M, h: 1.2, fontFace: T.fontCJK, fontSize: 40, bold: true, color: T.white, align: "center", margin: 0 });
  slide.addText(o.footnote, { x: M, y: 4.35, w: W - 2 * M, h: 0.6, fontFace: T.fontCJK, fontSize: 17, color: T.primaryLt, align: "center", margin: 0 });
}

/* ================= 1. 封面 ================= */
cover(p.addSlide(), {
  kicker: "使用者 SOP ・ 投影版",
  titleTop: "ClaudeCat",
  titleBottom: "桌面上的公司 AI 助手",
  subtitle: "聊天 ・ 文件問答 ・ 會議包 ・ 安全結束，三分鐘上手",
  date: "2026-07-21",
});

/* ========= 2. 能做什麼（1/2）========= */
let s = p.addSlide();
frame(s, "ClaudeCat 能做什麼（1／2）");
s.addText("多數同事無法直接上外網使用 LLM。ClaudeCat 把公司已提供的內網 AI 整合到桌面貓咪中，不必另開網頁、命令列或模型程式。",
  { x: M + 0.35, y: 1.25, w: W - 2 * M - 0.5, h: 0.5, fontFace: T.fontCJK, fontSize: 15, color: T.muted, valign: "middle", margin: 0 });
{
  const chatLines = ["右鍵 →「交談（LLM 介面）…」", "多輪對話、對話紀錄、匯出 Markdown"];
  const extra = [on("chat.attachments") ? "附件分析" : null,
                 on("chat.export_pptx") ? "簡報大綱匯出 PPTX" : null].filter(Boolean);
  if (extra.length) chatLines.push(extra.join("、"));
  const docLines = ["右鍵 →「文件助手…」", "PDF／Word／PowerPoint／Excel"];
  docLines.push("摘要、流程 SOP、表格整理" + (on("documents.compare") ? "、比較文件" : ""));
  cardGrid(s, [
    on("quick_question") && { title: "快速提問", lines: ["點一下貓咪，輸入問題按 Enter", "整理工作重點、解釋錯誤訊息", "短答留在氣泡，長答自動展開卡片"] },
    { title: "LLM 交談介面", lines: chatLines },
    on("documents") && { title: "分析文件", lines: docLines },
    on("documents") && { title: "文件問答與來源引用", lines: ["回答只能使用找到的證據", "附頁碼、段落、投影片或儲存格範圍", "文件未提及時會明確說明"] },
  ].filter(Boolean));
}

/* ========= 3. 能做什麼（2/2）========= */
s = p.addSlide();
frame(s, "ClaudeCat 能做什麼（2／2）");
cardGrid(s, [
  on("documents.meeting_pack") && { title: "文件會議包", lines: ["一鍵：摘要 → 會議重點 → Markdown", "可加英文翻譯；可取消、失敗可重試"] },
  on("json") && { title: "JSON 工具", lines: ["Format／Minify／Validate／JSONPath", "本機處理，完全不呼叫模型"] },
  on("translate") && { title: "翻譯工具", lines: ["英／繁中／簡中，可自動偵測來源", "保護程式碼、SQL、API path 與檔名"] },
  { title: "桌寵 ・ Skin" + (on("schedule") ? " ・ 排程" : ""),
    lines: ["拖曳移動、系統匣顯示／隱藏", "三種外觀" + (on("schedule") ? "；每日／每週／每小時提醒" : "")] },
].filter(Boolean), { y0: 1.35, h: 2.15, gapY: 2.35 });
note(s, "使用邊界：聊天與文件回答使用公司設定的內網 LLM。" +
  ((on("usage.claude") || on("usage.codex"))
    ? "Claude／Codex 用量功能完全獨立、預設關閉。" : "") +
  "使用者不需外網帳號。", 6.1);

/* ========= 4. 目前使用的模型 ========= */
s = p.addSlide();
frame(s, "目前使用的模型");
let y = lead(s, "使用公司設定的內網模型，使用者不需選擇");
card(s, { x: M + 0.35, y: y + 0.1, w: 11.6, h: 2.45, title: "使用者不必做的事", lines: [
  "不需要外網帳號、API Key，也不需要自行挑選模型",
  "聊天、文件問答與翻譯都使用公司統一的預設模型",
  "模型以直接、快速產出回答為主",
], bodySize: 15.5 });
card(s, { x: M + 0.35, y: y + 2.75, w: 11.6, h: 2.05, title: "哪些功能不呼叫模型", lines: [
  "JSON 的格式化、驗證、搜尋與 JSONPath 為本機確定性工具",
  (on("usage.claude") || on("usage.codex"))
    ? "Claude／Codex 用量僅是可選顯示，聊天不會呼叫 Claude 或 Codex"
    : "聊天與文件功能只使用公司內網模型",
], bodySize: 15.5 });
note(s, "本簡報不列出內網網址、模型名稱、API Key 或其他連線憑證。", 6.75);

/* ========= 5. Agenda ========= */
s = p.addSlide();
frame(s, "Agenda");
steps(s, [
  on("quick_question") && "快速提問與長回答",
  "切換到 LLM 交談介面",
  on("documents") && "分析文件、文件問答與來源引用",
  on("documents.meeting_pack") && "文件會議包：一鍵產出可交付的 Markdown",
  "桌寵管理、Skin" + (on("schedule") ? "、排程" : "") + "與安全結束",
].filter(Boolean), { y: 1.85, gap: 0.92, size: 19 });

/* ========= 6. 快速提問 ========= */
if (on("quick_question")) {

s = p.addSlide();
frame(s, "快速提問");
y = lead(s, "一般問題，不必另開聊天視窗");
steps(s, ["點一下桌面貓咪。", "在旁邊輸入問題後按 Enter。", "短答案直接顯示成氣泡。"], { y: y + 0.35, gap: 0.95, size: 17 });
note(s, "範例：今天的工作重點怎麼整理？", 5.6);
}

/* ========= 7. 長回答 ========= */
s = p.addSlide();
frame(s, "長回答");
y = lead(s, "需要細節時，展開成貓咪旁的卡片");
card(s, { x: M + 0.35, y: y + 0.25, w: 11.6, h: 2.6, title: "卡片可以做什麼", lines: ["可複製答案", "可繼續追問", "完成後可收合"], bodySize: 16 });
note(s, "範例：SQL Review、文件重點整理。", 5.9);

/* ========= 8. LLM 交談介面 ========= */
s = p.addSlide();
frame(s, "切換到 LLM 交談介面");
y = lead(s, "需要多輪對話或工具箱時，開啟完整介面");
steps(s, ["右鍵點選桌面貓咪。", "選「交談（LLM 介面）…」。", "多輪對話，或切換 JSON／翻譯工具。"], { y: y + 0.1, gap: 0.72, size: 16 });
card(s, { x: M + 0.35, y: 4.35, w: 11.6, h: 2.0, title: "此介面也可使用", lines: [
  "側欄對話紀錄：回看或繼續之前的對話　　・　附件：加入文字或 Excel 檔案",
  "Markdown／程式碼複製　　・　簡報匯出 PPTX　　・　輸入 / 叫出快速提示詞",
], bodySize: 14.5 });
note(s, "快速問題仍建議直接點貓咪，較不打斷工作流程。", 6.6);

/* ========= 9. 分析文件與文件問答 ========= */
if (on("documents")) {

s = p.addSlide();
frame(s, "分析文件與文件問答");
y = lead(s, "把文件交給貓咪，再依來源提問");
steps(s, [
  "右鍵點貓咪，選「文件助手…」。",
  "選擇 PDF／Word／PowerPoint／Excel，等待本機索引完成。",
  "可執行摘要、流程 SOP、表格整理或比較文件。",
  "提問並查看答案下方的來源引用。",
], { y: y + 0.15, gap: 0.85, size: 16 });
note(s, "建議問題：誰需要批准？這份文件在說什麼？有哪些注意事項？", 5.85);
note(s, "提醒：文件未提及時，系統會明確表示無法依文件確認。", 6.55, T.alertRed);
}

/* ========= 10. 文件會議包 ========= */
if (on("documents.meeting_pack")) {

s = p.addSlide();
frame(s, "文件會議包");
lead(s, "一鍵把文件變成可交付的會議 Markdown");
// 步驟鏈
const chain = [
  ["retrieve_evidence", "找出證據"],
  ["summarize", "摘要"],
  ["meeting_notes", "會議重點"],
  ["translate", "可選翻譯"],
  ["export_markdown", "輸出成果"],
];
const bw = 2.18, bgap = 0.24, bx0 = M + 0.35;
chain.forEach(([id, label], i) => {
  const bx = bx0 + i * (bw + bgap);
  const optional = id === "translate";
  s.addShape(p.ShapeType.rect, { x: bx, y: 2.05, w: bw, h: 1.0, fill: { color: optional ? T.white : T.cardBg }, line: { color: optional ? T.primaryLt : T.cardLine, width: optional ? 1.25 : 0.75, dashType: optional ? "dash" : "solid" } });
  s.addText(id, { x: bx + 0.06, y: 2.16, w: bw - 0.12, h: 0.4, fontFace: T.fontCode, fontSize: 11, bold: true, color: T.violet, align: "center", valign: "middle", margin: 0 });
  s.addText(label, { x: bx + 0.06, y: 2.56, w: bw - 0.12, h: 0.4, fontFace: T.fontCJK, fontSize: 14, color: T.ink, align: "center", valign: "middle", margin: 0 });
  if (i < chain.length - 1) {
    s.addText("›", { x: bx + bw, y: 2.05, w: bgap, h: 1.0, fontFace: T.fontCJK, fontSize: 20, bold: true, color: T.primaryLt, align: "center", valign: "middle", margin: 0 });
  }
});
s.addText("狀態圖示：✓ 完成　● 執行中　○ 待執行　✕ 失敗", { x: M + 0.35, y: 3.2, w: 11.6, h: 0.4, fontFace: T.fontCJK, fontSize: 14, color: T.muted, margin: 0 });
card(s, { x: M + 0.35, y: 3.75, w: 5.6, h: 2.6, title: "操作", lines: [
  "先完成前一頁的文件分析", "需要英文版時勾選「加入英文翻譯」", "按「建立文件會議包」", "執行中可取消；失敗可重新執行",
], bodySize: 14 });
card(s, { x: M + 6.25, y: 3.75, w: 5.6, h: 2.6, title: "安全設計", lines: [
  "同一次失敗最多重試 3 次", "中途失敗保留「部分成果」", "標示抽樣涵蓋範圍與來源定位", "程式被強制關閉可直接重新執行",
], bodySize: 14 });
}

/* ========= 11. 清理 Workflow 歷史 ========= */
if (on("documents.meeting_pack")) {

s = p.addSlide();
frame(s, "清理 Workflow 歷史");
y = lead(s, "成果會累積在本機，可自行清理");
steps(s, [
  "在文件助手上方按「清理 Workflow 歷史」。",
  "確認提示後，清除已結束的 Run 與 Markdown 成果。",
  "執行中的工作會保留，不會被清掉。",
], { y: y + 0.3, gap: 0.9, size: 16.5 });
note(s, "系統另會自動保留最近的執行紀錄，不需每次手動清理。", 5.85);
}

/* ========= 12. 工具箱：JSON 與翻譯 ========= */
if (on("json") || on("translate")) {
s = p.addSlide();
frame(s, "工具箱：JSON 與翻譯");
card(s, { x: M + 0.35, y: 1.45, w: 5.6, h: 2.5, title: "JSON 工具（不需 LLM）", lines: [
  "Format／Minify／Validate", "搜尋與 JSONPath", "格式錯誤會顯示行與欄",
], bodySize: 15 });
card(s, { x: M + 6.25, y: 1.45, w: 5.6, h: 2.5, title: "翻譯工具（語意處理）", lines: [
  "來源可自動偵測或指定", "英／繁中／簡中，可用 ⇄ 互換", "一般／技術／商務／中英對照",
], bodySize: 15 });
card(s, { x: M + 0.35, y: 4.2, w: 11.5, h: 1.85, title: "翻譯會原樣保留的內容", lines: [
  "程式碼、SQL、JSON Key、API path 與檔名不會被翻譯",
], bodySize: 15.5 });
note(s, "JSON 工具在 LLM 離線時仍可完全使用。", 6.3);

}

/* ========= 13. 切換 Skin ========= */
s = p.addSlide();
frame(s, "切換 Skin");
y = lead(s, "可依個人偏好更換貓咪外觀");
steps(s, ["右鍵點選桌面貓咪。", "開啟「切換 Skin」子選單。", "選擇 bluecat、cowcat 或 ragdollcat。"], { y: y + 0.3, gap: 0.9, size: 16.5 });
note(s, "切換後立即生效，重新啟動後也會保留最後一次選擇。", 5.85);

/* ========= 14. 用量顯示（選用）========= */
if (on("usage.claude") || on("usage.codex")) {

s = p.addSlide();
frame(s, "用量顯示（選用）");
y = lead(s, "Claude／Codex 用量可個別開關");
card(s, { x: M + 0.35, y: y + 0.35, w: 11.6, h: 2.3, title: "重點", lines: [
  "不影響聊天或文件問答",
  "未安裝或未登入時顯示 No use，不會查詢",
], bodySize: 16 });
note(s, "此功能預設關閉，首次啟用需要在自己的電腦上同意。", 5.9);
}

/* ========= 15. 桌寵管理與排程 ========= */
s = p.addSlide();
frame(s, "桌寵管理與排程");
y = lead(s, "維持桌面工作習慣，不必一直開著聊天視窗");
card(s, { x: M + 0.35, y: y + 0.2, w: 11.6, h: 3.3, title: "可以做的事", lines: [
  "左鍵拖曳貓咪或用量徽章，可移到適合的位置；位置會保留",
  "系統匣可顯示／隱藏桌寵、快速提問、開啟文件助手與結束程式",
  "右鍵選「排程…」，可新增每日、每週或每小時提醒",
], bodySize: 16 });

/* ========= 16. 安全結束與常見提示 ========= */
s = p.addSlide();
frame(s, "安全結束與常見提示");
y = lead(s, "從系統匣安全關閉");
steps(s, ["在工作列右下角找到 ClaudeCat 圖示。", "右鍵選「結束」。", "確認貓咪已從桌面消失。"], { y: y + 0.1, gap: 0.78, size: 16 });
card(s, { x: M + 0.35, y: 4.5, w: 11.6, h: 1.85, title: "常見提示", lines: [
  "缺少模型／服務請聯絡 IT　　・　掃描型 PDF 需要 OCR",
  "文件無資料時，請改問文件確實出現的內容",
], bodySize: 14.5 });

/* ========= 結尾 ========= */
closing(p.addSlide(), {
  kicker: "ClaudeCat 使用者 SOP",
  headline: "直接點貓咪提問",
  footnote: "文件助手會附來源　・　關閉請用系統匣",
});

p.writeFile({ fileName: "使用者SOP_投影版.pptx" }).then((f) => console.log("WROTE", f));
