// static/offline.js - IndexedDB cache for toilet data
const DB_NAME = 'toilet-map-cache';
const DB_VERSION = 1;
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('toilets')) {
        db.createObjectStore('toilets', { keyPath: 'place_id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
window.cacheToiletData = async function(data) {
  const db = await openDB();
  const tx = db.transaction('toilets', 'readwrite');
  const store = tx.objectStore('toilets');
  // Store first 200 to keep it small
  data.slice(0, 200).forEach(t => store.put(t));
  await new Promise(r => tx.oncomplete = r);
};
window.getCachedToiletCount = async function() {
  const db = await openDB();
  const tx = db.transaction('toilets', 'readonly');
  const store = tx.objectStore('toilets');
  return new Promise(r => {
    const req = store.count();
    req.onsuccess = () => r(req.result);
    req.onerror = () => r(0);
  });
};
