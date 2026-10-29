#!/usr/bin/env python3
# Claude Desktop 汉化助手（由 install-linux.sh 调用；也可单独运行调试）
# 支持 4.x（前端打包在 ion-dist.asar、桌面壳词典在 app.asar 内）与 3.x（明文目录）两种布局。
# 用法: ZH_RESOURCES=... ZH_BACKUP=... ZH_LANG=... python3 install-linux.py install|reset|check
#      python3 install-linux.py set-locale <config.json 路径>   # 以目标用户身份运行
import json, os, re, sys, hashlib, struct, shutil, subprocess, posixpath

RESOURCES = os.environ.get('ZH_RESOURCES', '')
BACKUP = os.environ.get('ZH_BACKUP', '')
LANG = os.environ.get('ZH_LANG', '')
MODE = sys.argv[1] if len(sys.argv) > 1 else ''

def p(msg): print(msg, flush=True)

def load(path):
    with open(path, encoding='utf-8') as f: return json.load(f)

def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1).encode('utf-8')

# ---------- 布局检测 ----------
def detect_layout():
    if os.path.isfile(os.path.join(RESOURCES, 'ion-dist.asar')): return 'asar4'
    if os.path.isfile(os.path.join(RESOURCES, 'ion-dist/i18n/en-US.json')): return 'dir3'
    raise SystemExit('未识别的资源布局：既没有 ion-dist.asar（4.x）也没有 ion-dist/i18n/en-US.json（3.x）。'
                     '请确认 Claude Desktop 安装完好，或用 --resources 指定正确的资源目录。')

def detect_version(layout):
    try:
        r = subprocess.run(['dpkg-query', '-W', '-f=${Version}', 'claude-desktop'],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return 'deb:' + r.stdout.strip()
    except Exception:
        pass
    if layout == 'asar4':
        blob = asar_entry(os.path.join(RESOURCES, 'ion-dist.asar'), '/i18n/en-US.json')[0]
    else:
        blob = open(os.path.join(RESOURCES, 'ion-dist/i18n/en-US.json'), 'rb').read()
    return 'hash:' + hashlib.sha256(blob).hexdigest()[:16]

# ---------- asar 读写 ----------
def asar_open(path):
    with open(path, 'rb') as f:
        head = f.read(16)
    json_len = int.from_bytes(head[12:16], 'little')
    with open(path, 'rb') as f:
        f.seek(16)
        header = json.loads(f.read(json_len).decode('utf-8'))
    data = open(path, 'rb').read()
    data_start = 8 + int.from_bytes(head[4:8], 'little')
    return data, header, data_start

def asar_find(header, path):
    node = header
    for seg in path.strip('/').split('/'):
        if not isinstance(node, dict) or 'files' not in node or seg not in node['files']:
            return None
        node = node['files'][seg]
    return node

def asar_entry(path, entry_path):
    data, header, data_start = asar_open(path)
    node = asar_find(header, entry_path)
    if node is None or 'size' not in node:
        raise RuntimeError('asar %s 中不存在条目 %s' % (os.path.basename(path), entry_path))
    if node.get('unpacked'):
        src = os.path.join(path + '.unpacked', entry_path.strip('/'))
        return open(src, 'rb').read(), header, -1, node
    off = int(node['offset'])
    return data[data_start + off:data_start + off + int(node['size'])], header, data_start, node

def asar_walk(header, prefix='', out=None):
    if out is None: out = []
    if isinstance(node := header, dict) and 'files' in node:
        for name, child in node['files'].items():
            asar_walk(child, prefix + '/' + name, out)
        return out
    if isinstance(header, dict) and 'size' in header:
        out.append((prefix, header))
    return out

def _integrity_node(blob, template=None):
    bs = int(template.get('blockSize', 4194304)) if isinstance(template, dict) else 4194304
    algo = template.get('algorithm', 'SHA256') if isinstance(template, dict) else 'SHA256'
    return {'algorithm': algo, 'hash': hashlib.sha256(blob).hexdigest(), 'blockSize': bs,
            'blocks': [hashlib.sha256(blob[i:i + bs]).hexdigest() for i in range(0, len(blob), bs)]}

def asar_rewrite(path, replacements=None, additions=None, removals=None):
    """重建 asar：replacements={条目路径:新bytes}；additions={新条目路径:bytes}；removals=[条目路径]。
    返回 (替换条目数, 新增条目数, 删除条目数)。写临时文件后原子替换。"""
    replacements = replacements or {}; additions = additions or {}; removals = set(removals or [])
    data, header, data_start = asar_open(path)
    tmpl = None
    for _pp, n in asar_walk(header):
        if isinstance(n.get('integrity'), dict) and n['integrity'].get('hash'):
            tmpl = n['integrity']; break
    for ep in list(replacements) + list(additions):
        if not ep.startswith('/') or '\\' in ep or '..' in ep.split('/'):
            raise RuntimeError('条目路径须为 / 开头且不含 .. 的绝对路径: ' + ep)
    entries = asar_walk(header)
    for ep in replacements:
        if asar_find(header, ep) is None:
            raise RuntimeError('asar 中不存在待替换条目: ' + ep)
    # 已存在的"新增"条目转为替换语义，保证条目计数一致
    for ep in list(additions):
        if asar_find(header, ep) is not None:
            replacements[ep] = additions.pop(ep)

    out = bytearray(); seen = {}; patched = 0
    for epath, node in entries:
        if epath in removals: continue
        if node.get('unpacked'):
            if epath in replacements:
                blob = replacements[epath]; patched += 1
                upath = os.path.join(path + '.unpacked', epath.strip('/'))
                os.makedirs(os.path.dirname(upath), exist_ok=True)
                with open(upath, 'wb') as f: f.write(blob)
                node['size'] = len(blob)
            continue
        if epath in replacements:
            blob = replacements[epath]; patched += 1
            node['offset'] = str(len(out)); node['size'] = len(blob)
            if isinstance(node.get('integrity'), dict):
                node['integrity'] = _integrity_node(blob, node['integrity'])
            out += blob
        else:
            key = (int(node.get('offset', 0)), int(node['size']))
            if key in seen:
                node['offset'] = str(seen[key]); continue
            blob = data[data_start + key[0]:data_start + key[0] + key[1]]
            seen[key] = len(out); node['offset'] = str(len(out))
            out += blob

    def parent_node(epath):
        node = header
        for seg in posixpath.dirname(epath).strip('/').split('/'):
            if not seg: continue
            node = node.setdefault('files', {}).setdefault(seg, {'files': {}})
            if 'files' not in node: node['files'] = {}
        return node

    for epath, blob in sorted(additions.items()):
        parent = parent_node(epath)
        name = posixpath.basename(epath)
        node = {'size': len(blob), 'offset': str(len(out)), 'integrity': _integrity_node(blob, tmpl)}
        parent['files'][name] = node
        out += blob

    removed = 0
    for epath in removals:
        parent = header
        segs = epath.strip('/').split('/')
        for seg in segs[:-1]:
            if not isinstance(parent, dict) or 'files' not in parent or seg not in parent['files']:
                parent = None; break
            parent = parent['files'][seg]
        if isinstance(parent, dict) and 'files' in parent and segs[-1] in parent['files']:
            del parent['files'][segs[-1]]; removed += 1

    hb = json.dumps(header, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    # 复刻官方格式：[4][@4][@8][hb] json NUL 填充(4 字节对齐) 数据
    pad = (-(len(hb) + 5)) % 4
    size8 = len(hb) + 5 + pad
    new = struct.pack('<4I', 4, size8 + 4, size8, len(hb)) + hb + b'\x00' + b'\x00' * pad + out
    new_data_start = 8 + size8 + 4

    # 自检：重新解析，逐条目校验 SHA-256 完整性与替换/新增内容
    jlen = int.from_bytes(new[12:16], 'little')
    hdr2 = json.loads(new[16:16 + jlen].decode('utf-8'))
    total = [0]; hash_bad = [0]
    for epath, node in asar_walk(hdr2):
        if node.get('unpacked'): continue
        total[0] += 1
        blob = new[new_data_start + int(node['offset']):new_data_start + int(node['offset']) + int(node['size'])]
        if isinstance(node.get('integrity'), dict) and node['integrity'].get('hash'):
            if hashlib.sha256(blob).hexdigest() != node['integrity']['hash']:
                hash_bad[0] += 1
        if epath in replacements and blob != replacements[epath]:
            raise RuntimeError('自检失败：替换条目内容不符 %s' % epath)
        if epath in additions and blob != additions[epath]:
            raise RuntimeError('自检失败：新增条目内容不符 %s' % epath)
    old_total = sum(1 for _ep, n in entries if not n.get('unpacked'))
    if total[0] != old_total + len(additions) - removed:
        raise RuntimeError('自检失败：条目数 %d（预期 %d）' % (total[0], old_total + len(additions) - removed))
    if hash_bad[0]:
        raise RuntimeError('自检失败：%d 个条目 hash 不符' % hash_bad[0])

    tmp = path + '.zh-tmp'
    with open(tmp, 'wb') as f: f.write(new)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return patched, len(additions), removed

# ---------- 状态 ----------
MANIFEST_PATH = os.path.join(BACKUP, 'manifest.json')
VERSION_PATH = os.path.join(BACKUP, '.version')

def read_state():
    if os.path.exists(MANIFEST_PATH):
        try: return load(MANIFEST_PATH)
        except Exception: pass
    return {'backups': [], 'deployed': []}

def backup_file(state, rel):
    src = os.path.join(RESOURCES, rel)
    dst = os.path.join(BACKUP, rel)
    if not os.path.isfile(src): return
    if rel in state['backups'] or rel in state['deployed']: return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    state['backups'].append(rel)

def mark_deployed(state, rel):
    if rel not in state['deployed']:
        state['deployed'].append(rel)

def save_state(state):
    os.makedirs(BACKUP, exist_ok=True)
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump({'backups': state['backups'], 'deployed': state['deployed']},
                  f, ensure_ascii=False, indent=1)

# ---------- 词典校验（与 3.x 相同） ----------
def strip_icu(value):
    s = str(value)
    res = ''; i = 0
    while i < len(s):
        if s[i] == '{':
            depth = 0; j = i
            while j < len(s):
                if s[j] == '{': depth += 1
                elif s[j] == '}':
                    depth -= 1
                    if depth == 0: break
                j += 1
            if j < len(s) and re.match(r'^[A-Za-z_][A-Za-z0-9_.-]*,\s*(plural|selectordinal|select)\s*,', s[i+1:j]):
                res += '{__ICU__}'; i = j + 1; continue
        res += s[i]; i += 1
    return res

def _tokens(value):
    c = {}; st = strip_icu(value)
    for t in re.findall(r'<[^>]*>|\{[A-Za-z_][A-Za-z0-9_.-]*\}', st): c[t] = c.get(t, 0) + 1
    return c

def struct_ok(en, zh):
    a, b = str(en), str(zh)
    if a.count('{') != b.count('{') or a.count('}') != b.count('}'): return False
    if sorted(re.findall(r'<[^>]*>', a)) != sorted(re.findall(r'<[^>]*>', b)): return False
    if _tokens(a) != _tokens(b): return False
    return True

def merge_dict(en_map, zh_map):
    out = {}; translated = 0; fell_back = 0
    for k, en in en_map.items():
        zh = zh_map.get(k)
        if zh is not None and zh != en and struct_ok(en, zh):
            out[k] = zh; translated += 1
        else:
            if zh is not None and zh != en: fell_back += 1
            out[k] = en
    return out, translated, fell_back

def write_json_atomic(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.zh-tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)

# ---------- 版本无关 locale 规则（按内容匹配；与 Windows 安装器同源） ----------
LOCALE_RULES = [
    ('["en-US","de-DE","fr-FR","ko-KR', '["en-US","zh-CN","de-DE","fr-FR","ko-KR'),
    ('"en-US":{name:"English (United States)",localName:"English (United States)"}',
     '"zh-CN":{name:"Chinese (Simplified)",localName:"简体中文"},"en-US":{name:"English (United States)",localName:"English (United States)"}'),
    ('case"en-US":return["language","en"];', 'case"zh-CN":return["language","zh-CN"];case"en-US":return["language","en"];'),
    # Linux 版适配（压缩后的变量名随构建变化，按固定片段匹配）
    ('?"Plugins":"Customize"', '?"Plugins":"自定义"'),
    ('??"Local task"', '??"本地任务"'),
]

GUARD_RE = re.compile(
    r'(?<![A-Za-z0-9_$-])(?:as|code|command|component|displayName|glyph|icon|iconName|id|key|kind|leadingIcon|locale|name|path|role|source|state|status|trailingIcon|type|value|variant)\s*[:=]\s*$')

def build_js_rules():
    exact_rules = list(LOCALE_RULES)
    for rel in ('assets-manifest.json', 'hardcoded.json'):
        try:
            rules = load(os.path.join(LANG, rel))
            if rel == 'assets-manifest.json':
                rules = rules.get('patches', [])
            for r in rules:
                b, a = r.get('before', ''), r.get('after', '')
                if b and a and b != a: exact_rules.append((b, a))
        except FileNotFoundError:
            pass
    plain_map = {}
    try:
        for s, t in load(os.path.join(LANG, 'frontend-hardcoded.json')):
            if not s or s == t: continue
            if re.search(r'["\\=;{}\r\n`]', s) or re.search(r'["\\{}\r\n`]', t): continue
            plain_map[s] = t
    except FileNotFoundError:
        pass
    return exact_rules, plain_map

def patch_js_text(text, exact_rules, plain_map):
    updated = text
    exact_hits = 0
    for before, after in exact_rules:
        if before in updated and after not in updated:
            exact_hits += updated.count(before)
            updated = updated.replace(before, after)
    plain_hits = 0
    if plain_map:
        for q in ('"', "'", '`'):
            qq = re.escape(q)
            pat = re.compile(qq + r'((?:\\.|[^' + qq + r'\\])*)' + qq)
            hits = [0]
            def sub(m, _q=q, _hits=hits, _cur=updated):
                v = m.group(1)
                if v not in plain_map: return m.group(0)
                prefix = _cur[max(0, m.start() - 96):m.start()]
                if GUARD_RE.search(prefix): return m.group(0)
                _hits[0] += 1
                return _q + plain_map[v] + _q
            updated = pat.sub(sub, updated)
            plain_hits += hits[0]
    return updated, exact_hits, plain_hits

# ---------- 4.x：ion-dist.asar 补丁 ----------
def patch_ion_dist(state):
    ion = os.path.join(RESOURCES, 'ion-dist.asar')
    data, header, data_start = asar_open(ion)

    fe_en = json.loads(asar_entry(ion, '/i18n/en-US.json')[0].decode('utf-8'))
    fe_dict = load(os.path.join(LANG, 'linux/dictionary.json'))
    fe_out, translated, fe_fallback = merge_dict(fe_en, fe_dict)
    repl = {}
    add = {'/i18n/zh-CN.json': json_bytes(fe_out)}
    remove = []

    ov = {k: v for k, v in load(os.path.join(LANG, 'linux/overrides.json')).items() if k in fe_en}
    if ov: add['/i18n/zh-CN.overrides.json'] = json_bytes(ov)
    elif asar_find(header, '/i18n/zh-CN.overrides.json') is not None:
        remove.append('/i18n/zh-CN.overrides.json')

    dyn = load(os.path.join(LANG, 'dynamic/zh-CN.json'))
    dyn_node = asar_find(header, '/i18n/dynamic/en-US.json')
    if dyn_node is not None:
        dyn_en = json.loads(asar_entry(ion, '/i18n/dynamic/en-US.json')[0].decode('utf-8'))
        dyn = {k: v for k, v in dyn.items() if k in dyn_en}
    add['/i18n/dynamic/zh-CN.json'] = json_bytes(dyn)

    exact_rules, plain_map = build_js_rules()
    patched_files = 0; exact_hits = 0; plain_hits = 0
    for epath, node in asar_walk(header):
        if not epath.endswith('.js') or node.get('unpacked'): continue
        if not (epath.startswith('/assets/v1/') or epath.startswith('/assets/')): continue
        off = int(node['offset'])
        blob = data[data_start + off:data_start + off + int(node['size'])]
        try:
            text = blob.decode('utf-8')
        except UnicodeDecodeError:
            continue
        updated, eh, ph = patch_js_text(text, exact_rules, plain_map)
        if updated == text: continue
        repl[epath] = updated.encode('utf-8')
        patched_files += 1; exact_hits += eh; plain_hits += ph

    backup_file(state, 'ion-dist.asar')
    p('· 前端词典：%d/%d 键已翻译（%d 键因英文原文变化暂回退英文）' % (translated, len(fe_en), fe_fallback))
    p('· JS 规则：修改 %d 个文件（精确规则 %d 处，文字规则 %d 处）' % (patched_files, exact_hits, plain_hits))
    patched, added, removed = asar_rewrite(ion, repl, add, remove)
    mark_deployed(state, 'ion-dist.asar#zh-CN')  # 仅记录，重置时整档恢复
    return len(fe_en), translated

def patch_app_asar(state):
    asar = os.path.join(RESOURCES, 'app.asar')
    data, header, data_start = asar_open(asar)
    repl = {}; add = {}

    # 桌面壳词典：app.asar 内 resources/i18n/<locale>.json
    sh_en_node = asar_find(header, '/resources/i18n/en-US.json')
    if sh_en_node is not None:
        sh_en = json.loads(asar_entry(asar, '/resources/i18n/en-US.json')[0].decode('utf-8'))
        sh_dict = load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
        sh_out, sh_translated, sh_fallback = merge_dict(sh_en, sh_dict)
        add['/resources/i18n/zh-CN.json'] = json_bytes(sh_out)
        p('· 桌面壳词典：%d/%d 键已翻译（%d 键回退英文）' % (sh_translated, len(sh_en), sh_fallback))
    else:
        p('· app.asar 内未找到桌面壳词典 resources/i18n/en-US.json，跳过桌面壳汉化')

    # 桌面语言映射：zh → zh-CN
    if b'id:"id-ID",zh:"zh-CN"}' in data:
        p('· app.asar 桌面语言映射：已打过补丁')
    else:
        target = None; occurrences = 0
        for epath, node in asar_walk(header):
            if node.get('unpacked'): continue
            off = int(node['offset'])
            blob = data[data_start + off:data_start + off + int(node['size'])]
            occurrences += blob.count(b'id:"id-ID"}')
            if b'id:"id-ID"}' in blob and target is None:
                target = (epath, blob)
        if target is None:
            p('· app.asar 中未找到 locale 映射（版本结构可能已变），已跳过；语言仍可从菜单选择')
        elif occurrences != 1:
            p('· app.asar 中 locale 映射出现 %d 次（预期 1 次），为保证安全已跳过' % occurrences)
        else:
            epath, blob = target
            repl[epath] = blob.replace(b'id:"id-ID"}', b'id:"id-ID",zh:"zh-CN"}')
            p('· app.asar 桌面语言映射：将打补丁（zh → zh-CN）')

    if not repl and not add:
        return
    backup_file(state, 'app.asar')
    asar_rewrite(asar, repl, add)

# ---------- 3.x：明文目录补丁（旧版兼容） ----------
def patch_dir3_assets(state):
    assets = os.path.join(RESOURCES, 'ion-dist/assets/v1')
    if not os.path.isdir(assets):
        p('· 未找到前端资源目录，跳过 JS 规则'); return
    exact_rules, plain_map = build_js_rules()
    quote_patterns = []
    for q in ('"', "'", '`'):
        qq = re.escape(q)
        quote_patterns.append((q, re.compile(qq + r'((?:\\.|[^' + qq + r'\\])*)' + qq)))
    names = os.listdir(assets)
    files = sorted(f for f in names if f.endswith('.js'))
    zst = [f for f in names if f.endswith('.js.zst')]
    if zst:
        p('· 注意：发现 %d 个 .js.zst 文件，其中内容未打补丁' % len(zst))
    patched_files = 0; exact_hits = 0; plain_hits = 0
    for name in files:
        path = os.path.join(assets, name)
        with open(path, encoding='utf-8') as f: text = f.read()
        updated, eh, ph = patch_js_text(text, exact_rules, plain_map)
        if updated == text: continue
        rel = 'ion-dist/assets/v1/' + name
        backup_file(state, rel)
        with open(path, 'w', encoding='utf-8') as f: f.write(updated)
        patched_files += 1; exact_hits += eh; plain_hits += ph
    p('· JS 规则：修改 %d 个文件（精确规则 %d 处，文字规则 %d 处）' % (patched_files, exact_hits, plain_hits))

def patch_asar_locale_only(state):
    """3.x 布局的 app.asar 语言映射补丁（原样保留旧逻辑）。"""
    asar = os.path.join(RESOURCES, 'app.asar')
    data = open(asar, 'rb').read()
    json_len = int.from_bytes(data[12:16], 'little')
    header = json.loads(data[16:16 + json_len].decode('utf-8'))
    data_start = 8 + int.from_bytes(data[4:8], 'little')
    if b'id:"id-ID",zh:"zh-CN"}' in data:
        p('· app.asar 桌面语言映射：已打过补丁'); return
    entries = []
    def walk(node):
        if isinstance(node, dict) and 'files' in node:
            for c in node['files'].values(): walk(c)
            return
        if isinstance(node, dict) and 'size' in node and 'offset' in node:
            entries.append((node, int(node['offset']), int(node['size'])))
    walk(header)
    target = None; occurrences = 0
    for node, off, size in entries:
        blob = data[data_start + off: data_start + off + size]
        occurrences += blob.count(b'id:"id-ID"}')
        if b'id:"id-ID"}' in blob and target is None:
            target = (node, blob)
    if target is None:
        p('· app.asar 中未找到 locale 映射（版本结构可能已变），已跳过；语言仍可从菜单选择'); return
    if occurrences != 1:
        p('· app.asar 中 locale 映射出现 %d 次（预期 1 次），为保证安全已跳过' % occurrences); return
    node, blob = target
    patched = blob.replace(b'id:"id-ID"}', b'id:"id-ID",zh:"zh-CN"}')

    out = bytearray()
    seen = {}
    for n, off, size in entries:
        if n is node:
            n['size'] = len(patched)
            n['offset'] = str(len(out))
            if isinstance(n.get('integrity'), dict):
                integ = n['integrity']
                bs = int(integ.get('blockSize', 4194304))
                integ['hash'] = hashlib.sha256(patched).hexdigest()
                integ['blocks'] = [hashlib.sha256(patched[i:i + bs]).hexdigest()
                                   for i in range(0, len(patched), bs)]
            out += patched
            continue
        key = (off, size)
        if key in seen:
            n['offset'] = str(seen[key]); continue
        n['offset'] = str(len(out))
        seen[key] = len(out)
        out += data[data_start + off: data_start + off + size]
    hb = json.dumps(header, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    pad = (-(len(hb) + 5)) % 4
    size8 = len(hb) + 5 + pad
    new = struct.pack('<4I', 4, size8 + 4, size8, len(hb)) + hb + b'\x00' + b'\x00' * pad + out
    new_data_start = 8 + size8 + 4

    jlen = int.from_bytes(new[12:16], 'little')
    hdr2 = json.loads(new[16:16 + jlen].decode('utf-8'))
    hits = [0]; total = [0]; hash_bad = [0]
    def walk2(n):
        if isinstance(n, dict) and 'files' in n:
            for c in n['files'].values(): walk2(c)
        elif isinstance(n, dict) and 'offset' in n:
            total[0] += 1
            start = new_data_start + int(n['offset'])
            blob = new[start:start + int(n['size'])]
            if b'id:"id-ID",zh:"zh-CN"}' in blob: hits[0] += 1
            if isinstance(n.get('integrity'), dict) and n['integrity'].get('hash'):
                if hashlib.sha256(blob).hexdigest() != n['integrity']['hash']:
                    hash_bad[0] += 1
    walk2(hdr2)
    if total[0] != len(entries) or hits[0] != 1 or hash_bad[0]:
        raise RuntimeError('asar 重建自检失败（条目 %d/%d，命中 %d，hash 错误 %d）'
                           % (total[0], len(entries), hits[0], hash_bad[0]))
    backup_file(state, 'app.asar')
    tmp = asar + '.zh-tmp'
    with open(tmp, 'wb') as f: f.write(new)
    os.replace(tmp, asar)
    p('· app.asar 桌面语言映射：已打补丁（zh → zh-CN）')

def do_install_dir3(state):
    # 四层中文资源（明文目录版）
    fe_en = load(os.path.join(RESOURCES, 'ion-dist/i18n/en-US.json'))
    fe_dict = load(os.path.join(LANG, 'linux/dictionary.json'))
    fe_out, translated, fe_fallback = merge_dict(fe_en, fe_dict)
    backup_file(state, 'ion-dist/i18n/zh-CN.json')
    write_json_atomic(os.path.join(RESOURCES, 'ion-dist/i18n/zh-CN.json'), fe_out)
    mark_deployed(state, 'ion-dist/i18n/zh-CN.json')
    save_state(state)

    ov = {k: v for k, v in load(os.path.join(LANG, 'linux/overrides.json')).items() if k in fe_en}
    ov_path = os.path.join(RESOURCES, 'ion-dist/i18n/zh-CN.overrides.json')
    if ov:
        write_json_atomic(ov_path, ov)
        mark_deployed(state, 'ion-dist/i18n/zh-CN.overrides.json')
    elif os.path.exists(ov_path):
        os.remove(ov_path)

    dyn = load(os.path.join(LANG, 'dynamic/zh-CN.json'))
    dyn_en_path = os.path.join(RESOURCES, 'ion-dist/i18n/dynamic/en-US.json')
    if os.path.exists(dyn_en_path):
        dyn_en = load(dyn_en_path)
        dyn = {k: v for k, v in dyn.items() if k in dyn_en}
    write_json_atomic(os.path.join(RESOURCES, 'ion-dist/i18n/dynamic/zh-CN.json'), dyn)
    mark_deployed(state, 'ion-dist/i18n/dynamic/zh-CN.json')

    sh_en_path = os.path.join(RESOURCES, 'en-US.json')
    if os.path.exists(sh_en_path):
        sh_dict = load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
        sh_out, sh_translated, sh_fallback = merge_dict(load(sh_en_path), sh_dict)
        backup_file(state, 'zh-CN.json')
        write_json_atomic(os.path.join(RESOURCES, 'zh-CN.json'), sh_out)
        mark_deployed(state, 'zh-CN.json')
        p('· 桌面壳词典：%d/%d 键已翻译（%d 键回退英文）' % (sh_translated, len(sh_en), sh_fallback))
    save_state(state)

    p('· 前端词典：%d/%d 键已翻译（%d 键因英文原文变化暂回退英文）' % (translated, len(fe_en), fe_fallback))
    patch_dir3_assets(state)
    save_state(state)
    try:
        patch_asar_locale_only(state)
    except Exception as e:
        p('· app.asar 补丁出错（%s），已跳过，不影响其余汉化' % e)
    save_state(state)

# ---------- install / reset / check ----------
def do_install():
    layout = detect_layout()
    version = detect_version(layout)
    os.makedirs(BACKUP, exist_ok=True)
    state = read_state()
    old_version = ''
    if os.path.exists(VERSION_PATH):
        with open(VERSION_PATH, encoding='utf-8') as f: old_version = f.read().strip()
    if old_version and old_version != version:
        p('· 检测到 Claude 已更新（%s → %s）：清除旧备份，按当前版本重新打补丁' % (old_version, version))
        shutil.rmtree(BACKUP, ignore_errors=True)
        os.makedirs(BACKUP, exist_ok=True)
        state = {'backups': [], 'deployed': []}
    if old_version != version:
        with open(VERSION_PATH, 'w', encoding='utf-8') as f: f.write(version)

    if layout == 'asar4':
        patch_ion_dist(state)
        save_state(state)
        patch_app_asar(state)
    else:
        do_install_dir3(state)

    save_state(state)
    p('')
    p('✔ 汉化完成。启动 Claude，从头像/用户菜单进入“语言”，选择“简体中文”。')

def do_reset():
    state = read_state()
    if not state['backups'] and not state['deployed']:
        p('· 没有可恢复的内容（尚未安装过汉化）'); return
    for rel in state['backups']:
        src = os.path.join(BACKUP, rel)
        dst = os.path.join(RESOURCES, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            p('· 已恢复 %s' % rel)
    for rel in state['deployed']:
        if rel in state['backups'] or '#' in rel: continue  # asar 内部部署项随整档恢复
        dst = os.path.join(RESOURCES, rel)
        if os.path.isfile(dst):
            os.remove(dst)
            p('· 已移除 %s' % rel)
    for f in (MANIFEST_PATH, VERSION_PATH):
        if os.path.exists(f): os.remove(f)
    shutil.rmtree(BACKUP, ignore_errors=True)
    p('✔ 已恢复英文原版。')

def do_check():
    layout = detect_layout()
    version = detect_version(layout)
    p('· 资源目录: %s' % RESOURCES)
    p('· 布局: %s' % ('4.x（ion-dist.asar）' if layout == 'asar4' else '3.x（明文目录）'))
    p('· 当前版本: %s' % version)
    if layout == 'asar4':
        ion = os.path.join(RESOURCES, 'ion-dist.asar')
        node = asar_find(asar_open(ion)[1], '/i18n/zh-CN.json')
        if node is not None:
            blob = asar_entry(ion, '/i18n/zh-CN.json')[0]
            p('· 前端 zh-CN.json: 已部署（%d 键）' % len(json.loads(blob.decode('utf-8'))))
        else:
            p('· 前端 zh-CN.json: 未部署')
        data, header, data_start = asar_open(ion)
        whitelist = False; namemap = False
        for epath, n in asar_walk(header):
            if whitelist and namemap: break
            if not epath.endswith('.js') or n.get('unpacked'): continue
            off = int(n['offset'])
            blob = data[data_start + off:data_start + off + int(n['size'])]
            if b'["en-US","zh-CN","de-DE"' in blob: whitelist = True
            if b'"zh-CN":{name:"Chinese (Simplified)"' in blob: namemap = True
        p('· 前端语言白名单: %s' % ('已加入 zh-CN' if whitelist else '未打补丁'))
        p('· 前端语言名称映射: %s' % ('已加入 zh-CN' if namemap else '未打补丁'))
        asar = os.path.join(RESOURCES, 'app.asar')
        adata = open(asar, 'rb').read()
        p('· app.asar 语言映射: %s' % ('已打补丁' if b'id:"id-ID",zh:"zh-CN"}' in adata else '未打补丁'))
        sh = asar_find(asar_open(asar)[1], '/resources/i18n/zh-CN.json')
        if sh is not None:
            blob = asar_entry(asar, '/resources/i18n/zh-CN.json')[0]
            p('· 桌面壳 zh-CN.json: 已部署（%d 键）' % len(json.loads(blob.decode('utf-8'))))
        else:
            p('· 桌面壳 zh-CN.json: 未部署')
    else:
        fe = os.path.join(RESOURCES, 'ion-dist/i18n/zh-CN.json')
        if os.path.exists(fe):
            p('· 前端 zh-CN.json: 已部署（%d 键）' % len(load(fe)))
        else:
            p('· 前端 zh-CN.json: 未部署')
        sh = os.path.join(RESOURCES, 'zh-CN.json')
        if os.path.exists(sh):
            p('· 桌面壳 zh-CN.json: 已部署（%d 键）' % len(load(sh)))
        else:
            p('· 桌面壳 zh-CN.json: 未部署')
        whitelist = False
        assets = os.path.join(RESOURCES, 'ion-dist/assets/v1')
        if os.path.isdir(assets):
            for name in os.listdir(assets):
                if not name.endswith('.js'): continue
                try:
                    with open(os.path.join(assets, name), encoding='utf-8') as f: t = f.read()
                except Exception: continue
                if '["en-US","zh-CN","de-DE"' in t:
                    whitelist = True; break
        p('· 前端语言白名单: %s' % ('已加入 zh-CN' if whitelist else '未打补丁'))
        with open(os.path.join(RESOURCES, 'app.asar'), 'rb') as f: blob = f.read()
        p('· app.asar 语言映射: %s' % ('已打补丁' if b'id:"id-ID",zh:"zh-CN"}' in blob else '未打补丁'))
    if os.path.exists(VERSION_PATH):
        with open(VERSION_PATH, encoding='utf-8') as f: v = f.read().strip()
        p('· 补丁记录版本: %s%s' % (v, '（与当前一致）' if v == version else '（与当前不同，建议重跑 install）'))

def set_locale(path):
    """把用户 config.json 的 locale 写为 zh-CN（保留其余配置项）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cfg = {}
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f: cfg = json.load(f)
        except Exception:
            cfg = {}
    cfg['locale'] = 'zh-CN'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

if MODE in ('install', 'reset', 'check') and not (RESOURCES and BACKUP and LANG):
    raise SystemExit('缺少环境变量 ZH_RESOURCES / ZH_BACKUP / ZH_LANG（正常使用请运行 install-linux.sh）')
if MODE == 'install': do_install()
elif MODE == 'reset': do_reset()
elif MODE == 'check': do_check()
elif MODE == 'set-locale':
    if len(sys.argv) < 3: raise SystemExit('set-locale 需要 config.json 路径参数')
    set_locale(sys.argv[2])
else: raise SystemExit('未知模式: ' + MODE)
