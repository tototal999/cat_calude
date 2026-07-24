/**
 * 建置期插圖產生器（IT 端執行，不隨產品發布）。
 *
 * 呼叫 Gemini 影像模型（Nano Banana）產生封面／結語的通用插圖，存成 PNG 後由
 * sop-deck-gen.js 嵌進簡報。使用者端拿到的是已含圖的靜態 pptx，執行期不會有任何
 * 外部呼叫——這也是為什麼這件事放在建置期而不是產品裡。
 *
 * 送出的只有本檔案清單裡的提示詞，不含任何公司文件或使用者資料。
 *
 * 用法：
 *   set GEMINI_API_KEY=...        （PowerShell: $env:GEMINI_API_KEY="..."）
 *   node tools/gen-illustrations.js          已存在的圖會跳過，不重複計費
 *   node tools/gen-illustrations.js --force  全部重新產生
 *   node tools/gen-illustrations.js cover    只產生指定 id
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const MANIFEST = path.join(__dirname, "illustration-prompts.json");
const OUT_DIR = path.join(ROOT, "assets", "illustrations");
const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions";

const args = process.argv.slice(2);
const force = args.includes("--force");
const only = args.filter((a) => !a.startsWith("--"));

function fail(message) {
  console.error("\n[錯誤] " + message + "\n");
  process.exit(1);
}

const apiKey = (process.env.GEMINI_API_KEY || "").trim();
if (!apiKey) {
  fail(
    "找不到環境變數 GEMINI_API_KEY。\n" +
    "  PowerShell:  $env:GEMINI_API_KEY=\"金鑰\"\n" +
    "  cmd.exe:     set GEMINI_API_KEY=金鑰   （不要加引號，引號會被算進值裡）\n" +
    "  金鑰只從環境變數讀取，不會寫入專案、不會出現在 log。"
  );
}
// HTTP 標頭只接受 latin-1；非 ASCII 會在送出時丟出難懂的 ByteString 錯誤，
// 而最常見的原因是把說明文字（例如「你的金鑰」）當成金鑰貼進去了。
const badChar = [...apiKey].find((c) => c.charCodeAt(0) > 127);
if (badChar) {
  fail(
    `GEMINI_API_KEY 含有非 ASCII 字元「${badChar}」，這不是有效的金鑰。\n` +
    "  常見原因：把說明文字當成金鑰貼上了，請填入實際金鑰值。"
  );
}
if (apiKey.startsWith('"') || apiKey.endsWith('"')) {
  fail("GEMINI_API_KEY 前後包含引號。cmd.exe 的 set 不需要引號，請去掉後重試。");
}
// 刻意不檢查金鑰前綴：AI Studio 的 AIza… 與 OAuth 的 AQ.… 實測都能用，
// 用前綴猜格式只會產生假警報。真的無效時 API 會回 401，訊息本身就夠清楚。

const manifest = JSON.parse(fs.readFileSync(MANIFEST, "utf8"));
const model = manifest._model || "gemini-3.1-flash-image";
const style = manifest._style ? `\n\nStyle: ${manifest._style}` : "";
// 目前 API 只接受 image/jpeg（送 image/png 會回 400）。放在 manifest 裡，
// 日後支援其他格式時改一行即可。
const mimeType = manifest._mime_type || "image/jpeg";
const ext = mimeType === "image/png" ? "png" : "jpg";

/** 從回應中取出第一張圖；容錯處理不同版本的欄位位置。 */
function extractImage(body) {
  const direct = body?.output_image;
  if (direct?.data) return direct;
  for (const step of body?.steps || []) {
    for (const block of step?.content || []) {
      if (block?.type === "image" && block?.data) return block;
    }
  }
  return null;
}

async function generate(item) {
  const target = path.join(OUT_DIR, `${item.id}.${ext}`);
  if (!force && fs.existsSync(target)) {
    console.log(`  跳過 ${item.id}（已存在，未呼叫 API）`);
    return "skipped";
  }
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: { "x-goog-api-key": apiKey, "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      input: [{ type: "text", text: item.prompt + style }],
      response_format: {
        type: "image",
        mime_type: mimeType,
        aspect_ratio: item.aspect_ratio || "1:1",
      },
    }),
  });

  const text = await response.text();
  if (!response.ok) {
    // 不回顯請求內容，避免把金鑰帶進 log
    throw new Error(`HTTP ${response.status}：${text.slice(0, 400)}`);
  }
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    throw new Error(`回應不是有效 JSON：${text.slice(0, 200)}`);
  }
  const image = extractImage(body);
  if (!image) {
    throw new Error(
      "回應中找不到影像資料。API 格式可能已變更，回應最外層欄位：" +
      Object.keys(body || {}).join(", ")
    );
  }
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(target, Buffer.from(image.data, "base64"));
  const kb = Math.round(fs.statSync(target).size / 1024);
  console.log(`  產生 ${item.id}.${ext}（${kb} KB，${image.mime_type || mimeType}）`);
  return "created";
}

(async () => {
  const items = manifest.images.filter((i) => !only.length || only.includes(i.id));
  if (!items.length) fail(`清單中找不到指定的 id：${only.join(", ")}`);
  console.log(`模型 ${model}，共 ${items.length} 張：`);

  let created = 0, skipped = 0;
  for (const item of items) {
    try {
      const result = await generate(item);
      result === "created" ? created++ : skipped++;
    } catch (error) {
      console.error(`  失敗 ${item.id}：${error.message}`);
      process.exitCode = 1;
    }
  }
  console.log(`\n完成：新增 ${created}、跳過 ${skipped}。輸出於 assets/illustrations/`);
  console.log("接著重跑 node tools/sop-deck-gen.js 讓簡報帶上插圖。");
})();
