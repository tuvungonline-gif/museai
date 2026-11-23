"""Validate and install the prebuilt account UI, switching index.html last."""
import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


def install(archive, root, backup=None, check=False):
    dist = Path(root) / 'canvas' / 'dist'
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:
                raise ValueError('Duong dan tep giao dien khong hop le.')
        if z.testzip() is not None:
            raise ValueError('Goi giao dien bi hong.')
        html = z.read('index.html').decode('utf-8')
        if 'data-muse-account-ui="1"' not in html:
            raise ValueError('Goi giao dien khong dung phien ban.')
        assets = re.findall(r'(?:src|href)="/(assets/[^"?]+|prompt-library-reset-v1\.js)"', html)
        if not assets or any(name not in names for name in assets):
            raise ValueError('Thieu tai nguyen giao dien.')
        if check:
            print('Goi giao dien hop le.')
            return
        if backup:
            Path(backup).mkdir(parents=True, exist_ok=True)
            shutil.copy2(dist / 'index.html', Path(backup) / 'canvas-index.html')
        for name in names:
            if name == 'index.html' or name.endswith('/'):
                continue
            target = dist / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
        temp = dist / 'index.html.account-new'
        temp.write_text(html, encoding='utf-8')
        temp.replace(dist / 'index.html')
        print('Da cai giao dien Quan ly tai khoan.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--archive', required=True)
    p.add_argument('--root', required=True)
    p.add_argument('--backup')
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    install(args.archive, args.root, args.backup, args.check)
