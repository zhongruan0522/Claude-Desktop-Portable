const fs = require("fs");
const path = require("path");
const https = require("https");

const root = path.resolve(__dirname, "..");
const source = JSON.parse(fs.readFileSync(path.join(root, "app/resources/ion-dist/i18n/en-US.json"), "utf8"));
const outputDir = path.join(__dirname, "zh-CN");
const outputPath = path.join(outputDir, "ko-KR.json");
const cachePath = path.join(outputDir, "icu-cache.json");
const current = JSON.parse(fs.readFileSync(outputPath, "utf8"));
const cache = fs.existsSync(cachePath) ? JSON.parse(fs.readFileSync(cachePath, "utf8")) : {};
const delimiter = "\n";

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

function requestTranslation(query) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ q: query, source: "en", target: "zh", format: "text" });
    const req = https.request("https://translate.adminforge.de/translate", {
      method: "POST",
      headers: { "User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
    }, (response) => {
      let text = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { text += chunk; });
      response.on("end", () => {
        if (response.statusCode !== 200) { reject(new Error(`HTTP ${response.statusCode}`)); return; }
        try {
          const json = JSON.parse(text);
          if (!json.translatedText) { reject(new Error("no translated text")); return; }
          resolve(String(json.translatedText));
        } catch (error) { reject(new Error(`invalid response: ${error.message}`)); }
      });
    });
    req.setTimeout(30000, () => req.destroy(new Error("translation timeout")));
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

async function translateQuery(query) {
  let last;
  for (let i = 1; i <= 5; i += 1) {
    try { return await requestTranslation(query); }
    catch (error) { last = error; await sleep(i * 2000); }
  }
  throw last;
}

function matchingBrace(text, start) {
  let depth = 0;
  for (let i = start; i < text.length; i += 1) {
    if (text[i] === "{") depth += 1;
    else if (text[i] === "}" && --depth === 0) return i;
  }
  return -1;
}

function commaAtTop(text, from) {
  let depth = 0;
  for (let i = from; i < text.length; i += 1) {
    if (text[i] === "{") depth += 1;
    else if (text[i] === "}") depth -= 1;
    else if (text[i] === "," && depth === 0) return i;
  }
  return -1;
}

function parseText(text, addFragment) {
  let result = "";
  let plain = "";
  const flush = () => {
    if (plain) {
      result += addFragment(plain);
      plain = "";
    }
  };

  for (let i = 0; i < text.length;) {
    if (text[i] === "{") {
      const end = matchingBrace(text, i);
      if (end < 0) { plain += text[i++]; continue; }
      const content = text.slice(i + 1, end);
      const firstComma = commaAtTop(content, 0);
      if (firstComma < 0) {
        flush();
        result += text.slice(i, end + 1);
        i = end + 1;
        continue;
      }
      const secondComma = commaAtTop(content, firstComma + 1);
      if (secondComma < 0) {
        // Number/date/time styles have one comma and are valid ICU syntax;
        // keep the entire expression intact so the formatter still receives
        // the original variable name.
        flush();
        result += text.slice(i, end + 1);
        i = end + 1;
        continue;
      }
      flush();
      const prefix = content.slice(0, secondComma + 1);
      const branches = content.slice(secondComma + 1);
      let rebuilt = "{" + prefix;
      let p = 0;
      while (p < branches.length) {
        const ws = branches.slice(p).match(/^\s*/)[0];
        rebuilt += ws;
        p += ws.length;
        if (p >= branches.length) break;
        const selector = branches.slice(p).match(/^(=?[A-Za-z0-9_-]+)/);
        if (!selector) { rebuilt += branches.slice(p); break; }
        rebuilt += selector[1];
        p += selector[1].length;
        const beforeBody = branches.slice(p).match(/^\s*/)[0];
        rebuilt += beforeBody;
        p += beforeBody.length;
        if (branches[p] !== "{") { rebuilt += branches.slice(p); break; }
        const bodyEnd = matchingBrace(branches, p);
        if (bodyEnd < 0) { rebuilt += branches.slice(p); break; }
        rebuilt += "{" + parseText(branches.slice(p + 1, bodyEnd), addFragment) + "}";
        p = bodyEnd + 1;
      }
      result += rebuilt + "}";
      i = end + 1;
      continue;
    }
    if (text[i] === "<") {
      const tagEnd = text.indexOf(">", i);
      if (tagEnd >= 0) { flush(); result += text.slice(i, tagEnd + 1); i = tagEnd + 1; continue; }
    }
    plain += text[i++];
  }
  flush();
  return result;
}

function shouldTranslate(value) {
  return /[A-Za-z]/.test(value) && !/^[A-Z0-9_./:+-]+$/.test(value);
}

function cleanFragmentTranslation(original, translated) {
  let result = String(translated);
  // The public service occasionally emits LibreOffice-style font control
  // groups around a leading `#` in ICU plural text. Those groups are not part
  // of the source fragment and would create extra ICU braces when restored.
  if (!/[{}]/.test(original)) result = result.replace(/\{\\[^}]*\}/g, "").replace(/[{}]/g, "");
  return result;
}

function tokenCounts(value) {
  const counts = {};
  for (const token of String(value).match(/<[^>]*>|\{[A-Za-z_][A-Za-z0-9_.-]*\}/g) || []) counts[token] = (counts[token] || 0) + 1;
  for (const match of String(value).matchAll(/\{([A-Za-z_][A-Za-z0-9_.-]*),\s*(number|date|time)\b/g)) {
    const token = `{${match[1]},${match[2]}}`;
    counts[token] = (counts[token] || 0) + 1;
  }
  for (const match of String(value).matchAll(/\{([A-Za-z_][A-Za-z0-9_.-]*),\s*(plural|selectordinal|select)\s*,/g)) {
    const token = `{${match[1]},${match[2]},}`;
    counts[token] = (counts[token] || 0) + 1;
  }
  return Object.fromEntries(Object.keys(counts).sort().map((key) => [key, counts[key]]));
}

function structureMatches(sourceValue, targetValue) {
  const sourceBraces = (String(sourceValue).match(/[{}]/g) || []).length;
  const targetBraces = (String(targetValue).match(/[{}]/g) || []).length;
  const tags = (value) => JSON.stringify((String(value).match(/<[^>]*>/g) || []).sort());
  return sourceBraces === targetBraces && tags(sourceValue) === tags(targetValue) &&
    JSON.stringify(tokenCounts(sourceValue)) === JSON.stringify(tokenCounts(targetValue));
}

const fragmentMap = new Map();
const skeletons = new Map();
for (const [key, value] of Object.entries(source)) {
  if (!shouldTranslate(value)) continue;
  if (current[key] !== value && structureMatches(value, current[key])) continue;
  const fragments = [];
  const skeleton = parseText(String(value), (fragment) => {
    const id = fragments.length;
    fragments.push(fragment);
    if (!fragmentMap.has(fragment)) fragmentMap.set(fragment, { id: fragmentMap.size, value: fragment });
    return `ZXQFRAG${id}QZX`;
  });
  if (fragments.length) skeletons.set(key, { skeleton, fragments });
}

function batches(entries) {
  const result = [];
  let batch = [];
  let length = 0;
  for (const entry of entries) {
    const size = entry.value.length + 2;
    if (batch.length && length + size > 1200) { result.push(batch); batch = []; length = 0; }
    if (entry.value.includes("\n")) {
      if (batch.length) { result.push(batch); batch = []; length = 0; }
      result.push([entry]);
      continue;
    }
    batch.push(entry);
    length += size;
  }
  if (batch.length) result.push(batch);
  return result;
}

async function main() {
  const entries = [...fragmentMap.values()].filter((entry) => !cache[entry.value]);
  const groups = batches(entries);
  console.log(`remaining strings ${entries.length}, batches ${groups.length}`);
  let cursor = 0;
  let completed = 0;
  const workers = Array.from({ length: 4 }, async () => {
    while (true) {
      const index = cursor++;
      if (index >= groups.length) return;
      const group = groups[index];
      let translated = null;
      try {
        const response = await translateQuery(group.map((entry) => entry.value).join(delimiter));
        const parts = response.split(delimiter);
        if (parts.length === group.length) translated = parts;
      } catch (error) {
        console.warn(`batch ${index}: ${error.message}`);
      }
      if (!translated) {
        translated = [];
        for (const entry of group) {
          try { translated.push(await translateQuery(entry.value)); }
          catch (error) { console.warn(`skip fragment: ${error.message}`); translated.push(entry.value); }
          await sleep(100);
        }
      }
      for (let i = 0; i < group.length; i += 1) cache[group[i].value] = cleanFragmentTranslation(group[i].value, translated[i] || group[i].value);
      fs.writeFileSync(cachePath, JSON.stringify(cache), "utf8");
      completed += 1;
      if (completed % 10 === 0 || completed === groups.length) console.log(`translated ${completed}/${groups.length} batches`);
    }
  });
  await Promise.all(workers);

  const result = { ...current };
  for (const [key, info] of skeletons) {
    let translated = info.skeleton;
    info.fragments.forEach((fragment, index) => {
      translated = translated.replace(`ZXQFRAG${index}QZX`, cache[fragment] || fragment);
    });
    result[key] = translated;
  }
  const json = JSON.stringify(Object.fromEntries(Object.keys(source).map((key) => [key, result[key] ?? source[key]])), null, 2) + "\n";
  fs.writeFileSync(outputPath, json, "utf8");
  fs.writeFileSync(path.join(outputDir, "en-US.json"), json, "utf8");
  fs.unlinkSync(cachePath);
  console.log(`wrote ${Object.keys(source).length} translations`);
}

main().catch((error) => { console.error(error.stack || error.message); process.exitCode = 1; });

