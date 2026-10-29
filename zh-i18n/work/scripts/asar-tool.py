#!/usr/bin/env python3
# asar 归档查看/解包小工具（仅本仓库同步流程使用）
# 用法:
#   asar-tool.py list <archive.asar> [前缀过滤]
#   asar-tool.py extract <archive.asar> <输出目录> [前缀过滤]
import json, os, re, sys, hashlib

def read_header(path):
    data = open(path, 'rb').read(64)
    json_len = int.from_bytes(data[12:16], 'little')
    f = open(path, 'rb')
    f.seek(16)
    header = json.loads(f.read(json_len).decode('utf-8'))
    data_start = 8 + int.from_bytes(data[4:8], 'little')
    return header, data_start, f

def walk(node, prefix, out):
    if isinstance(node, dict):
        if 'files' in node:
            for name, child in node['files'].items():
                walk(child, prefix + '/' + name, out)
            return
        if 'size' in node:
            out.append((prefix, int(node.get('offset', -1)), int(node['size']), node.get('unpacked', False)))

def main():
    mode, archive = sys.argv[1], sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 and mode == 'list' else None
    extract_to = sys.argv[3] if mode == 'extract' else None
    extract_prefix = sys.argv[4] if mode == 'extract' and len(sys.argv) > 4 else ''
    header, data_start, f = read_header(archive)
    entries = []
    walk(header, '', entries)
    if mode == 'list':
        n = 0
        for path, off, size, unpacked in entries:
            if prefix and not path.startswith(prefix):
                continue
            print('%s\t%s\t%d' % (path, 'unpacked' if unpacked else off, size))
            n += 1
        print('# %d entries (of %d)' % (n, len(entries)), file=sys.stderr)
    elif mode == 'extract':
        base = os.path.dirname(os.path.abspath(archive))
        for path, off, size, unpacked in entries:
            if extract_prefix and not path.startswith(extract_prefix):
                continue
            dst = os.path.join(extract_to, path.lstrip('/'))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if unpacked:
                src = os.path.join(base, archive + '.unpacked', path.lstrip('/'))
                with open(src, 'rb') as s, open(dst, 'wb') as d:
                    d.write(s.read())
            else:
                f.seek(data_start + off)
                with open(dst, 'wb') as d:
                    d.write(f.read(size))
        print('# extracted to %s' % extract_to, file=sys.stderr)
    else:
        raise SystemExit('未知模式: ' + mode)

if __name__ == '__main__':
    main()
