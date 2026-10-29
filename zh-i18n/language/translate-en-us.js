const fs = require("fs");
const path = require("path");
const https = require("https");

const root = path.resolve(__dirname, "..");
const inputPath = path.join(root, "app", "resources", "ion-dist", "i18n", "en-US.json");
const desktopChinesePath = path.join(root, "app", "resources", "zh-Hans.json");
const outputDir = path.join(__dirname, "zh-CN");
const outputPath = path.join(outputDir, "ko-KR.json");
const sourceNamedOutputPath = path.join(outputDir, "en-US.json");
const cachePath = path.join(outputDir, "translation-cache.json");
const finalizeOnly = process.argv.includes("--finalize");

const source = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const desktopChinese = JSON.parse(fs.readFileSync(desktopChinesePath, "utf8"));
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
  "No plugins yet. Plugins are bundles of skills and connectors. Add ready-made plugins from Anthropic or add your own from GitHub or a file.": "还没有插件。插件由技能和连接器组成。你可以添加 Anthropic 提供的现成插件，也可以从 GitHub 或文件添加自己的插件。",
  "Skills": "技能",
  "Connectors": "连接器",
  "General": "常规",
  "Privacy": "隐私",
  "Usage": "使用量",
  "Code": "代码",
  "Cowork": "Cowork",
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

const protectedWords = ["plural", "selectordinal", "select", "offset", "one", "other", "zero", "two", "few", "many"];
const markerPrefix = "ZXQPH";

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
    for (const word of protectedWords) {
      value = value.replace(new RegExp(`\\b${word}\\b`, "g"), put(word));
    }
  }
  value = value.replace(/[{}]/g, put);
  return { value, tokens };
}

function restore(text, tokens) {
  let value = String(text);
  for (const [token, original] of tokens) {
    value = value.split(token).join(original);
  }
  return value;
}

function shouldTranslate(value) {
  return /[A-Za-z]/.test(value) && !/^[A-Z0-9_./:+-]+$/.test(value);
}

function requestTranslation(query) {
  return new Promise((resolve, reject) => {
    const url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=" + encodeURIComponent(query);
    const request = https.get(url, { headers: { "User-Agent": "Mozilla/5.0" } }, (response) => {
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
          resolve((json[0] || []).map((part) => part[0] || "").join(""));
        } catch (error) {
          reject(new Error(`invalid translation response: ${error.message}`));
        }
      });
    });
    request.setTimeout(30000, () => request.destroy(new Error("translation timeout")));
    request.on("error", reject);
  });
}

async function translateBatch(entries) {
  const prepared = entries.map(([key, value]) => {
    const protectedValue = protect(value);
    return { key, value, protectedValue };
  });
  const query = prepared.map((entry) => entry.protectedValue.value).join("ZXQDELIMZX");
  for (let attempt = 1; attempt <= 6; attempt += 1) {
    try {
      const translated = await requestTranslation(query);
      const parts = translated.split("ZXQDELIMZX");
      if (parts.length !== prepared.length) {
        const individual = await Promise.all(prepared.map(async (entry) => {
          const translatedOne = await requestTranslation(entry.protectedValue.value);
          return [entry.key, restore(translatedOne, entry.protectedValue.tokens)];
        }));
        return individual;
      }
      return prepared.map((entry, index) => {
        const restored = restore(parts[index], entry.protectedValue.tokens);
        const originalTokens = entry.protectedValue.tokens.map(([token]) => token);
        if (originalTokens.some((token) => !parts[index].includes(token))) return [entry.key, entry.value];
        return [entry.key, restored];
      });
    } catch (error) {
      if (attempt === 6) throw error;
      await new Promise((resolve) => setTimeout(resolve, attempt * 10000));
    }
  }
  throw new Error("unreachable");
}

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const entries = Object.entries(source);
  const output = {};
  const pending = [];

  for (const [key, value] of entries) {
    if (Object.prototype.hasOwnProperty.call(desktopChinese, key)) {
      output[key] = desktopChinese[key];
    } else if (Object.prototype.hasOwnProperty.call(manual, value)) {
      output[key] = manual[value];
    } else if (Object.prototype.hasOwnProperty.call(cache, key)) {
      output[key] = cache[key];
    } else if (!shouldTranslate(value)) {
      output[key] = value;
    } else if (!finalizeOnly) {
      pending.push([key, value]);
    } else {
      output[key] = value;
    }
  }

  const batches = [];
  let batch = [];
  let batchLength = 0;
  for (const entry of pending) {
    const nextLength = batchLength + entry[1].length + 12;
    if (batch.length >= 70 || nextLength > 5000) {
      batches.push(batch);
      batch = [];
      batchLength = 0;
    }
    batch.push(entry);
    batchLength += entry[1].length + 12;
  }
  if (batch.length) batches.push(batch);

  let completed = 0;
  let nextBatch = 0;
  const workers = Array.from({ length: 1 }, async () => {
    while (true) {
      const index = nextBatch++;
      if (index >= batches.length) return;
      const translated = await translateBatch(batches[index]);
      for (const [key, value] of translated) {
        output[key] = value;
        cache[key] = value;
      }
      completed += 1;
      if (completed % 10 === 0 || completed === batches.length) {
        fs.writeFileSync(cachePath, JSON.stringify(cache));
        console.log(`translated ${completed}/${batches.length} batches`);
      }
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
