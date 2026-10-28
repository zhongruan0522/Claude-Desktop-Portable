const fs = require("fs");
const path = require("path");
const https = require("https");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "app", "resources", "ion-dist", "i18n", "en-US.json");
const outputDir = path.join(__dirname, "zh-CN");
const outputPath = path.join(outputDir, "ko-KR.json");
const sourceNamedOutputPath = path.join(outputDir, "en-US.json");
const cachePath = path.join(outputDir, "mymemory-cache.json");

const source = JSON.parse(fs.readFileSync(sourcePath, "utf8"));
const existing = fs.existsSync(outputPath) ? JSON.parse(fs.readFileSync(outputPath, "utf8")) : {};
const cache = fs.existsSync(cachePath) ? JSON.parse(fs.readFileSync(cachePath, "utf8")) : {};

const manual = {
  "Search": "搜索",
  "Search skills and plugins": "搜索技能和插件",
  "Discover": "发现",
  "Add": "添加",
  "Your plugins": "你的插件",
  "Add your first plugins": "添加你的第一个插件",
  "Give Claude role-level expertise with plugins.": "通过插件为 Claude 提供专业能力。",
  "This computer": "此电脑",
  "Import & export": "导入和导出",
  "Settings": "设置",
  "Plugins": "插件",
  "Add plugin": "添加插件",
  "Skills": "技能",
  "Connectors": "连接器",
  "General": "常规",
  "Privacy": "隐私",
  "Usage": "使用量",
  "Code": "代码",
  "Developer": "开发者",
  "Customize": "自定义",
  "System": "系统",
  "Appearance": "外观",
  "Display": "显示",
  "Font": "字体",
  "Interface font": "界面字体",
  "Code font": "代码字体",
  "Chat font": "对话字体",
  "Sessions": "会话",
  "Privacy settings": "隐私设置",
  "Privacy controls": "隐私控制",
  "Screen recording": "屏幕录制",
  "Help and support": "帮助和支持",
  "Display style": "显示样式",
  "Import and export": "导入和导出",
  "Light": "浅色",
  "Dark": "深色",
  "Small": "小",
  "Medium": "中",
  "Large": "大",
  "Compact": "紧凑",
  "Normal": "普通",
  "Detailed": "详细",
};

const markerPrefix = "ZXQPH";
// Newlines survive LibreTranslate's segmentation and provide an unambiguous
// separator for short labels. Multiline source strings are sent alone below.
const delimiter = "\n";
const protectedWords = ["plural", "selectordinal", "select", "offset", "one", "other", "zero", "two", "few", "many"];
const contactAddresses = [
  "codex@example.com",
  "translator@example.com",
  "a@b.com",
  "claude@example.com",
  "localizer@example.com",
  "translate@example.com",
];
const googleHosts = ["translate.googleapis.com", "translate.google.com"];
let googleHostIndex = 0;
let contactIndex = 0;

function protect(text) {
  const tokens = [];
  const put = (value) => {
    const token = `${markerPrefix}${tokens.length}QZX`;
    tokens.push([token, value]);
    return token;
  };
  let value = String(text);
  value = value.replace(/<[^>]*>/g, put);
  value = value.replace(/\{[A-Za-z_][A-Za-z0-9_.-]*\}/g, put);
  if (value.includes("{")) {
    for (const word of protectedWords) value = value.replace(new RegExp(`\\b${word}\\b`, "g"), put(word));
  }
  value = value.replace(/[{}]/g, put);
  return { value, tokens };
}

function restore(value, tokens) {
  let result = String(value);
  for (const [token, original] of tokens) result = result.split(token).join(original);
  return result;
}

function tokenCounts(value) {
  const counts = {};
  for (const token of String(value).match(/<[^>]*>|\{[A-Za-z_][A-Za-z0-9_.-]*\}/g) || []) counts[token] = (counts[token] || 0) + 1;
  return counts;
}

function validTranslation(original, translated) {
  const a = tokenCounts(original);
  const b = tokenCounts(translated);
  const normalize = (counts) => Object.fromEntries(Object.keys(counts).sort().map((key) => [key, counts[key]]));
  return JSON.stringify(normalize(a)) === JSON.stringify(normalize(b));
}

function shouldTranslate(value) {
  return /[A-Za-z]/.test(value) && !/^[A-Z0-9_./:+-]+$/.test(value);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function requestTranslation(query) {
  return new Promise((resolve, reject) => {
    if (query.length > 9000) {
      reject(new Error(`query too long (${query.length})`));
      return;
    }
    const url = "https://translate.adminforge.de/translate";
    const body = JSON.stringify({ q: query, source: "en", target: "zh", format: "text" });
    const request = https.request(url, {
      method: "POST",
      headers: {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(body),
      },
    }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        if (response.statusCode !== 200) {
          reject(new Error(`translation HTTP ${response.statusCode}`));
          return;
        }
        try {
          const json = JSON.parse(body);
          if (!json.translatedText) {
            reject(new Error("translation service returned no text"));
            return;
          }
          resolve(String(json.translatedText));
        } catch (error) {
          reject(new Error(`invalid translation response: ${error.message}`));
        }
      });
    });
    request.setTimeout(30000, () => request.destroy(new Error("translation timeout")));
    request.on("error", reject);
    request.write(body);
    request.end();
  });
}

async function requestWithRetry(query) {
  let lastError;
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    try {
      return await requestTranslation(query);
    } catch (error) {
      lastError = error;
      await sleep(Math.min(15000, attempt * 2500));
    }
  }
  throw lastError;
}

function makeBatches(entries) {
  const batches = [];
  let batch = [];
  let length = 0;
  for (const entry of entries) {
    if (entry.value.includes("\n")) {
      if (batch.length) {
        batches.push(batch);
        batch = [];
        length = 0;
      }
      batches.push([entry]);
      continue;
    }
    const size = entry.prepared.value.length + delimiter.length + 2;
    if (batch.length && length + size > 6000) {
      batches.push(batch);
      batch = [];
      length = 0;
    }
    if (!batch.length && size > 430) {
      batches.push([entry]);
      continue;
    }
    batch.push(entry);
    length += size;
  }
  if (batch.length) batches.push(batch);
  return batches;
}

async function translateBatch(batch) {
  const query = batch.map((entry) => entry.prepared.value).join(delimiter);
  try {
    const translated = await requestWithRetry(query);
    const parts = translated.split(delimiter).map((part) => part.trim());
    if (parts.length === batch.length && parts.every((part, index) => entryHasAllTokens(part, batch[index]))) {
      return batch.map((entry, index) => [entry.key, restore(parts[index], entry.prepared.tokens)]);
    }
  } catch (error) {
    // Fall through to the per-entry path. Long ICU messages may exceed the
    // service's query limit and will be retained in English for later repair.
  }

  const result = [];
  for (const entry of batch) {
    try {
      const translated = await requestWithRetry(entry.prepared.value);
      if (entryHasAllTokens(translated, entry)) result.push([entry.key, restore(translated, entry.prepared.tokens)]);
      else result.push([entry.key, entry.value]);
    } catch (error) {
      console.warn(`skip ${entry.key}: ${error.message}`);
      result.push([entry.key, entry.value]);
    }
    await sleep(100);
  }
  return result;
}

function entryHasAllTokens(translated, entry) {
  return entry.prepared.tokens.every(([token]) => translated.split(token).length - 1 === 1);
}

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const output = {};
  const pending = [];
  let kept = 0;

  for (const [key, value] of Object.entries(source)) {
    const old = existing[key];
    if (Object.prototype.hasOwnProperty.call(manual, value)) {
      output[key] = manual[value];
      continue;
    }
    if (typeof old === "string" && old !== value && validTranslation(value, old)) {
      output[key] = old;
      kept += 1;
      continue;
    }
    if (Object.prototype.hasOwnProperty.call(cache, key) && validTranslation(value, cache[key])) {
      output[key] = cache[key];
      kept += 1;
      continue;
    }
    if (!shouldTranslate(value)) {
      output[key] = value;
      continue;
    }
    const prepared = protect(value);
    pending.push({ key, value, prepared });
  }

  const batches = makeBatches(pending);
  console.log(`keeping ${kept}, translating ${pending.length} values in ${batches.length} batches`);
  let completed = 0;
  let nextBatch = 0;
  const workers = Array.from({ length: 4 }, async () => {
    while (true) {
      const index = nextBatch++;
      if (index >= batches.length) return;
      const result = await translateBatch(batches[index]);
      for (const [key, value] of result) {
        output[key] = value;
        cache[key] = value;
      }
      completed += 1;
      fs.writeFileSync(cachePath, JSON.stringify(cache), "utf8");
      if (completed % 25 === 0 || completed === batches.length) console.log(`translated ${completed}/${batches.length} batches`);
      await sleep(300);
    }
  });
  await Promise.all(workers);

  const ordered = {};
  for (const key of Object.keys(source)) ordered[key] = output[key] ?? source[key];
  const json = JSON.stringify(ordered, null, 2) + "\n";
  fs.writeFileSync(outputPath, json, "utf8");
  fs.writeFileSync(sourceNamedOutputPath, json, "utf8");
  fs.unlinkSync(cachePath);
  console.log(`wrote ${Object.keys(ordered).length} translations to ${outputPath}`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});





