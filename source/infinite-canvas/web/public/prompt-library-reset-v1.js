(function () {
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
