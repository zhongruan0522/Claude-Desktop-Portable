#!/usr/bin/env python3
# 验证 reset 后 asar 与当前解包官方原版逐字节完全一致
import hashlib, os, sys
from common5x import WORK, paths_for

P = paths_for()
RES = os.environ.get('ZH_RESOURCES', os.path.join(WORK, 'test-run/resources'))
BASE = P['deb_res']

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

ok = True
for name in ('app.asar', 'ion-dist.asar'):
    a = sha(os.path.join(RES, name))
    b = sha(os.path.join(BASE, name))
    same = (a == b)
    print('%s 与原版 %s 一致: %s' % (name, P['ver'], same))
    if not same:
        ok = False

if not ok:
    sys.exit(1)
