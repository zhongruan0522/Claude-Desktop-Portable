#!/usr/bin/env python3
# 验证 reset 后 asar 与原版完全一致
import sys, os, hashlib
sys.argv = ['install-linux.py', 'check']
RES = '/workspace/Claude Desktop/zh-i18n/work/test-resources'
os.environ['ZH_RESOURCES'] = RES
os.environ['ZH_BACKUP'] = '/workspace/Claude Desktop/zh-i18n/work/test-backup'
os.environ['ZH_LANG'] = '/workspace/Claude Desktop/zh-i18n/language/zh-CN'

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

base = '/workspace/Claude Desktop/zh-i18n/work/deb-5.11492.5/usr/lib/claude-desktop/resources'
for name in ('app.asar', 'ion-dist.asar'):
    a = sha(os.path.join(RES, name))
    b = sha(os.path.join(base, name))
    print('%s 与原版一致: %s' % (name, a == b))
