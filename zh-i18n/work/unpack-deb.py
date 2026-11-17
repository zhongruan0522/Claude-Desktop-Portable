#!/usr/bin/env python3
# 下载/解包官方最新 Claude Desktop Linux deb 包并提取三层 i18n 基线；或清理临时解包产物
# 用法:
#   python3 zh-i18n/work/unpack-deb.py              # 自动查询官方 APT 源最新版本、下载校验并解包提取
#   python3 zh-i18n/work/unpack-deb.py <file.deb>   # 使用本地 deb 包解包提取
#   python3 zh-i18n/work/unpack-deb.py clean        # 按 AGENTS.md 约定清理 deb 安装包、解包目录与中间产物
import glob, hashlib, os, shutil, subprocess, sys, urllib.request
from common5x import WORK, ver_key

APT_BASE = 'https://downloads.claude.ai/claude-desktop/apt/stable'
PACKAGES_URL = APT_BASE + '/dists/stable/main/binary-amd64/Packages'
ASAR_TOOL = os.path.join(WORK, 'scripts/asar-tool.py')
EXTRACT_FS = os.path.join(WORK, 'extract-frame-shell-en.py')

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def fetch_latest_meta():
    req = urllib.request.Request(PACKAGES_URL, headers={'User-Agent': 'curl/8.5.0'})
    text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
    pkgs = []
    cur = {}
    for line in text.splitlines():
        if not line.strip():
            if cur.get('Package') == 'claude-desktop' and 'Version' in cur:
                pkgs.append(cur)
            cur = {}
            continue
        if ':' in line and not line.startswith(' '):
            k, v = line.split(':', 1)
            cur[k.strip()] = v.strip()
    if cur.get('Package') == 'claude-desktop' and 'Version' in cur:
        pkgs.append(cur)
    if not pkgs:
        raise SystemExit('未能从官方 APT 索引解析到 claude-desktop 包信息')
    pkgs.sort(key=lambda d: ver_key(d['Version']))
    return pkgs[-1]

def download_deb(meta):
    ver = meta['Version']
    rel = meta['Filename']
    expected = meta['SHA256']
    dst = os.path.join(WORK, f'claude-desktop_{ver}_amd64.deb')
    if os.path.isfile(dst) and sha256_file(dst) == expected:
        print(f'· 已存在校验通过的 deb 包: {os.path.basename(dst)}')
        return dst, ver
    url = f'{APT_BASE}/{rel}'
    print(f'· 正在下载最新版本 {ver}: {url}')
    subprocess.run(['curl', '-fL', '-C', '-', '-o', dst, url], check=True)
    actual = sha256_file(dst)
    if actual != expected:
        raise SystemExit(f'SHA256 校验失败: 预期 {expected}, 实际 {actual}')
    print(f'· SHA256 校验通过: {actual}')
    return dst, ver

def unpack_all(deb_path, ver=None):
    if not ver:
        ver = subprocess.check_output(['dpkg-deb', '-f', deb_path, 'Version'], text=True).strip()
    deb_dir = os.path.join(WORK, f'deb-{ver}')
    res_dir = os.path.join(deb_dir, 'usr/lib/claude-desktop/resources')
    if not os.path.isfile(os.path.join(res_dir, 'ion-dist.asar')):
        print(f'· 解包 {os.path.basename(deb_path)} -> deb-{ver}/')
        shutil.rmtree(deb_dir, ignore_errors=True)
        subprocess.run(['dpkg-deb', '-x', deb_path, deb_dir], check=True)
    ion_out = os.path.join(WORK, f'ion-i18n-{ver}')
    app_out = os.path.join(WORK, f'app-i18n-{ver}')
    fs_out = os.path.join(WORK, f'app-frame-shell-{ver}')
    for out_dir, asar_name, prefix in (
        (ion_out, 'ion-dist.asar', '/i18n'),
        (app_out, 'app.asar', '/resources/i18n'),
        (fs_out, 'app.asar', '/resources/frame/shell'),
    ):
        shutil.rmtree(out_dir, ignore_errors=True)
        subprocess.run([sys.executable, ASAR_TOOL, 'extract', os.path.join(res_dir, asar_name), out_dir, prefix], check=True)
    env = dict(os.environ, CLAUDE_VER=ver)
    subprocess.run([sys.executable, EXTRACT_FS], env=env, check=True)
    print(f'✔ 版本 {ver} 基线提取完成')

def clean_all():
    patterns = [
        '*.deb', 'deb-*', 'deb4', 'ion-i18n-*', 'app-i18n-*', 'app-frame-shell-*',
        'test*-resources', 'test*-backup', '.zh-CN-backup', 'batches', 'results', 'tm-*.json',
    ]
    removed = []
    for pat in patterns:
        for p in sorted(glob.glob(os.path.join(WORK, pat))):
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            removed.append(os.path.relpath(p, WORK))
    print('✔ 已清理临时文件:', ', '.join(removed) if removed else '（无残留）')

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else 'latest'
    if arg == 'clean':
        clean_all()
    elif arg == 'latest':
        meta = fetch_latest_meta()
        print(f"· 官方 APT 最新版本: {meta['Version']}")
        deb_path, ver = download_deb(meta)
        unpack_all(deb_path, ver)
    else:
        if not os.path.isfile(arg):
            raise SystemExit('未找到指定 deb 文件: ' + arg)
        unpack_all(os.path.abspath(arg))

if __name__ == '__main__':
    main()
