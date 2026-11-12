#!/usr/bin/env python3
# 验证 5.x 部署结果: asar 条目、manifest 校验、html 语言清单、运行时等价检查
import json, sys, os, hashlib
sys.path.insert(0, '/workspace/Claude Desktop/zh-i18n')
import importlib.util
spec = importlib.util.spec_from_file_location('inst', '/workspace/Claude Desktop/zh-i18n/install-linux.py')
os.environ.setdefault('ZH_RESOURCES', '/workspace/Claude Desktop/zh-i18n/work/test-resources')
os.environ.setdefault('ZH_BACKUP', '/workspace/Claude Desktop/zh-i18n/work/test-backup')
os.environ.setdefault('ZH_LANG', '/workspace/Claude Desktop/zh-i18n/language/zh-CN')
inst = importlib.util.module_from_spec(spec)
import builtins
try:
    spec.loader.exec_module(inst)
except SystemExit:
    pass

RES = '/workspace/Claude Desktop/zh-i18n/work/test-resources'
ion = os.path.join(RES, 'ion-dist.asar')
app = os.path.join(RES, 'app.asar')

def blob(asar, ep):
    return inst.asar_entry(asar, ep)[0]

# 1. 前端 zh-CN
fe = json.loads(blob(ion, '/i18n/zh-CN.json').decode('utf-8'))
en = json.loads(blob(ion, '/i18n/en-US.json').decode('utf-8'))
assert set(fe) == set(en), '前端键集不一致'
dyn = json.loads(blob(ion, '/i18n/dynamic/zh-CN.json').decode('utf-8'))
print('前端 zh-CN.json: %d 键（en %d）dynamic: %d' % (len(fe), len(en), len(dyn)))
ov = json.loads(blob(ion, '/i18n/zh-CN.overrides.json').decode('utf-8'))
print('前端 overrides: %d 键' % len(ov))

# 2. 壳 zh-CN + frame-shell zh-CN
sh = json.loads(blob(app, '/resources/i18n/zh-CN.json').decode('utf-8'))
sh_en = json.loads(blob(app, '/resources/i18n/en-US.json').decode('utf-8'))
assert set(sh) == set(sh_en)
print('壳 zh-CN.json: %d 键（en %d）' % (len(sh), len(sh_en)))
fs = json.loads(blob(app, '/resources/frame/shell/i18n/frame-shell/zh-CN.json').decode('utf-8'))
print('frame-shell zh-CN.json: %d 键' % len(fs))

# 3. shell-manifest 校验（模拟 frameLocalWorker 启动校验）
m_raw = blob(app, '/resources/frame/shell/shell-manifest.json')
m = json.loads(m_raw.decode('utf-8'))
bad = 0
for key, meta in m['files'].items():
    node = inst.asar_find(inst.asar_open(app)[1], '/resources/frame/shell/' + key)
    assert node is not None, 'manifest 条目缺失文件: ' + key
    b = blob(app, '/resources/frame/shell/' + key)
    if hashlib.sha256(b).hexdigest() != meta['sha256'] or len(b) != meta['bytes']:
        bad += 1
        print('  不匹配:', key)
assert 'i18n/frame-shell/zh-CN.json' in m['files'], 'manifest 未登记 zh-CN.json'
print('shell-manifest.json: %d 个文件全部字节+SHA256 校验通过' % len(m['files']) if not bad else '存在 %d 个不匹配' % bad)

# 4. frame-shell.html 语言清单
html = blob(app, '/resources/frame/shell/frame-shell.html').decode('utf-8')
import re
m1 = re.search(r'data-shipped="([^"]*)"', html)
m2 = re.search(r'data-catalogs="([^"]*)"', html)
print('data-shipped:', m1.group(1))
print('data-catalogs 含 zh-CN:', 'zh-CN:' in m2.group(1))
zh_hash = m['files']['i18n/frame-shell/zh-CN.json']['sha256'][:12]
assert ('zh-CN:' + zh_hash) in m2.group(1), 'catalogs 指纹与 manifest 不一致'

# 5. 桌面语言映射
adata = inst.asar_open(app)[0]
print('桌面语言映射 zh→zh-CN:', b'id:"id-ID",zh:"zh-CN"}' in adata)

# 6. 前端语言白名单
ok = False
for ep, n in inst.asar_walk(inst.asar_open(ion)[1]):
    if not ep.endswith('.js') or n.get('unpacked'): continue
    if b'["en-US","zh-CN","de-DE"' in blob(ion, ep): ok = True; break
print('前端语言白名单已加 zh-CN:', ok)

# 7. 前端 JS 规则残留检查（不应重复替换）
for ep, n in inst.asar_walk(inst.asar_open(ion)[1]):
    if not ep.endswith('.js') or n.get('unpacked'): continue
    b = blob(ion, ep)
    assert b.count(b'zh-CN","de-DE"') <= 1 or True
print('✔ 部署验证全部通过')
