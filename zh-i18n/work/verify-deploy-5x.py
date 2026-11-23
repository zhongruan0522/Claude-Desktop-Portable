#!/usr/bin/env python3
# 验证 5.x 部署结果: asar 条目、manifest 校验、html 语言清单、运行时等价检查
import hashlib, importlib.util, json, os, re
from common5x import ROOT, WORK, LANG

RES = os.environ.get('ZH_RESOURCES', os.path.join(WORK, 'test-run/resources'))
os.environ.setdefault('ZH_RESOURCES', RES)
os.environ.setdefault('ZH_BACKUP', os.path.join(os.path.dirname(RES), '.zh-CN-backup'))
os.environ.setdefault('ZH_LANG', LANG)

spec = importlib.util.spec_from_file_location('inst', os.path.join(ROOT, 'install-linux.py'))
inst = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(inst)
except SystemExit:
    pass

ion_path = os.path.join(RES, 'ion-dist.asar')
app_path = os.path.join(RES, 'app.asar')
ion_data, ion_hdr, ion_ds = inst.asar_open(ion_path)
app_data, app_hdr, app_ds = inst.asar_open(app_path)

def entry_bytes(asar_path, data, hdr, ds, ep):
    node = inst.asar_find(hdr, ep)
    if node is None or 'size' not in node:
        raise AssertionError(f'{os.path.basename(asar_path)} 缺失条目: {ep}')
    if node.get('unpacked'):
        return open(os.path.join(asar_path + '.unpacked', ep.strip('/')), 'rb').read()
    off = int(node['offset'])
    return data[ds + off:ds + off + int(node['size'])]

def ion_blob(ep):
    return entry_bytes(ion_path, ion_data, ion_hdr, ion_ds, ep)

def app_blob(ep):
    return entry_bytes(app_path, app_data, app_hdr, app_ds, ep)

# 1. 前端 zh-CN
fe = json.loads(ion_blob('/i18n/zh-CN.json').decode('utf-8'))
en = json.loads(ion_blob('/i18n/en-US.json').decode('utf-8'))
assert set(fe) == set(en), '前端键集不一致'
dyn = json.loads(ion_blob('/i18n/dynamic/zh-CN.json').decode('utf-8'))
print('前端 zh-CN.json: %d 键（en %d）dynamic: %d' % (len(fe), len(en), len(dyn)))
ov = json.loads(ion_blob('/i18n/zh-CN.overrides.json').decode('utf-8'))
print('前端 overrides: %d 键' % len(ov))

# 2. 壳 zh-CN + frame-shell zh-CN
sh = json.loads(app_blob('/resources/i18n/zh-CN.json').decode('utf-8'))
sh_en = json.loads(app_blob('/resources/i18n/en-US.json').decode('utf-8'))
assert set(sh) == set(sh_en)
print('壳 zh-CN.json: %d 键（en %d）' % (len(sh), len(sh_en)))
fs = json.loads(app_blob('/resources/frame/shell/i18n/frame-shell/zh-CN.json').decode('utf-8'))
print('frame-shell zh-CN.json: %d 键' % len(fs))

# 3. shell-manifest 校验（模拟 frameLocalWorker 启动校验）
m = json.loads(app_blob('/resources/frame/shell/shell-manifest.json').decode('utf-8'))
bad = 0
for key, meta in m['files'].items():
    b = app_blob('/resources/frame/shell/' + key)
    if hashlib.sha256(b).hexdigest() != meta['sha256'] or len(b) != meta['bytes']:
        bad += 1
        print('  不匹配:', key)
assert 'i18n/frame-shell/zh-CN.json' in m['files'], 'manifest 未登记 zh-CN.json'
assert not bad, '存在 %d 个不匹配' % bad
print('shell-manifest.json: %d 个文件全部字节+SHA256 校验通过' % len(m['files']))

# 4. frame-shell.html 语言清单
html = app_blob('/resources/frame/shell/frame-shell.html').decode('utf-8')
m1 = re.search(r'data-shipped="([^"]*)"', html)
m2 = re.search(r'data-catalogs="([^"]*)"', html)
print('data-shipped:', m1.group(1))
print('data-catalogs 含 zh-CN:', 'zh-CN:' in m2.group(1))
zh_hash = m['files']['i18n/frame-shell/zh-CN.json']['sha256'][:12]
assert ('zh-CN:' + zh_hash) in m2.group(1), 'catalogs 指纹与 manifest 不一致'

# 5. 桌面语言映射
assert b'id:"id-ID",zh:"zh-CN"}' in app_data, '桌面语言映射未打补丁'
print('桌面语言映射 zh→zh-CN: True')

# 6. 前端语言白名单 & 重复补丁防护
ok = False
for ep, n in inst.asar_walk(ion_hdr):
    if not ep.endswith('.js') or n.get('unpacked'):
        continue
    off = int(n['offset'])
    b = ion_data[ion_ds + off:ion_ds + off + int(n['size'])]
    if b'["en-US","zh-CN","de-DE"' in b:
        ok = True
    assert b'["en-US","zh-CN","zh-CN"' not in b, f'重复白名单注入: {ep}'
assert ok, '前端语言白名单未加 zh-CN'
print('前端语言白名单已加 zh-CN: True')
print('✔ 部署验证全部通过')
