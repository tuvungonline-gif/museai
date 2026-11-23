"""Remove legacy prompt sources from the installed Canvas without rebuilding it."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
from datetime import datetime


RESET_JS = r'''(function () {
  const version = 'muse:prompt-library-reset:20261123-v1';
  try {
    if (!localStorage.getItem(version + ':sources')) {
      localStorage.removeItem('infinite-canvas:prompt_source_store_v2');
      localStorage.setItem(version + ':sources', 'done');
    }
    if (localStorage.getItem(version + ':cache')) return;
    const request = indexedDB.open('infinite-canvas');
    request.onupgradeneeded = function () {
      request.transaction.abort();
      localStorage.setItem(version + ':cache', 'done');
    };
    request.onsuccess = function () {
      const db = request.result;
      if (!db.objectStoreNames.contains('prompt_cache')) {
        db.close();
        localStorage.setItem(version + ':cache', 'done');
        return;
      }
      const tx = db.transaction('prompt_cache', 'readwrite');
      tx.objectStore('prompt_cache').clear();
      tx.oncomplete = function () {
        db.close();
        localStorage.setItem(version + ':cache', 'done');
      };
      tx.onabort = tx.onerror = function () { db.close(); };
    };
  } catch (error) { console.warn('Prompt library reset could not finish', error); }
})();
'''


def reset(root):
    dist = Path(root) / 'canvas' / 'dist'
    index = dist / 'index.html'
    html = index.read_text(encoding='utf-8')
    match = re.search(r'<script[^>]*type="module"[^>]*src="(/assets/[^"?]+\.js)"', html)
    if not match:
        raise RuntimeError('Khong tim thay tep giao dien Canvas. Chua thay doi gi.')
    bundle = dist / match.group(1).lstrip('/')
    original = bundle.read_text(encoding='utf-8')
    patched, count = re.subn(
        r'\bconst (\w+)=\[(\w+)\("banana-prompt-quicker".*?\];',
        lambda m: 'const ' + m.group(1) + '=[];', original, count=1,
    )
    if not count:
        if 'prompt-library-empty-' in bundle.name and 'banana-prompt-quicker' not in original:
            print('Thu vien da duoc lam trong. Khong xoa lai loi nhac moi.')
            return
        raise RuntimeError('Phien ban giao dien khac ban da kiem tra. Chua thay doi gi.')
    digest = hashlib.sha256(patched.encode()).hexdigest()[:12]
    new_name = 'prompt-library-empty-' + digest + '.js'
    new_bundle = dist / 'assets' / new_name
    new_bundle.write_text(patched, encoding='utf-8')
    (dist / 'prompt-library-reset-v1.js').write_text(RESET_JS, encoding='utf-8')
    updated = html.replace(match.group(1), '/assets/' + new_name)
    updated = updated.replace('<head>', '<head>\n        <script src="/prompt-library-reset-v1.js"></script>', 1)
    backup = Path(root) / ('canvas-index-before-prompt-reset-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.html')
    shutil.copy2(index, backup)
    temp = index.with_suffix('.html.new')
    temp.write_text(updated, encoding='utf-8')
    temp.replace(index)
    print('Da bo toan bo nguon loi nhac cu. Moi trinh duyet se don thu vien khi mo lai web.')
    print('Tai lai trang bang Ctrl+F5. Khong can khoi dong lai Muse API hay Canvas.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    reset(parser.parse_args().root)
