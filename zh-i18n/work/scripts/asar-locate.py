#!/usr/bin/env python3
# 在 asar 归档的数据区定位字符串, 输出所在文件与上下文
# 用法: asar-locate.py <archive.asar> <字符串> [上下文字节数] [最多命中数]
import json, sys

archive, needle = sys.argv[1], sys.argv[2]
ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 100
maxhits = int(sys.argv[4]) if len(sys.argv) > 4 else 3

data = open(archive, 'rb').read()
json_len = int.from_bytes(data[12:16], 'little')
header = json.loads(data[16:16 + json_len].decode('utf-8'))
data_start = 8 + int.from_bytes(data[4:8], 'little')

entries = []
def walk(node, prefix):
    if isinstance(node, dict):
        if 'files' in node:
            for name, child in node['files'].items(): walk(child, prefix + '/' + name)
            return
        if 'size' in node and not node.get('unpacked'):
            entries.append((prefix, data_start + int(node.get('offset', -1)), int(node['size'])))
walk(header, '')
entries.sort(key=lambda e: e[1])

nb = needle.encode()
hits = 0
for path, start, size in entries:
    blob = data[start:start + size]
    pos = blob.find(nb)
    while pos != -1 and hits < maxhits:
        lo = max(0, pos - ctx); hi = min(len(blob), pos + len(nb) + ctx)
        print('### %s (+%d)' % (path, pos))
        print(blob[lo:hi].decode('utf-8', 'replace'))
        print()
        hits += 1
        pos = blob.find(nb, pos + 1)
    if hits >= maxhits: break
if hits == 0: print('(no hits)')
