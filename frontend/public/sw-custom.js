// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0
//
// Custom service worker additions — injected alongside the Workbox-generated SW.
// Handles:
//   1. Server push notifications (VAPID)
//   2. Background sync for offline attendance queue
//   3. Periodic background sync for offline class notifications

// ── Push notifications ───────────────────────────────────────────────────────

self.addEventListener('push', function (event) {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: 'Chronos Ledger', body: event.data.text(), urgencyTag: 'general' };
  }

  const options = {
    body: payload.body || 'New organization notification',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/icon-72x72.png',
    vibrate: [200, 100, 200],
    data: { url: payload.targetUrl || '/' },
    tag: payload.urgencyTag || 'general-broadcast',
    requireInteraction: payload.urgencyTag === 'SUMMON' || payload.urgencyTag === 'GUEST_HANDSHAKE_REQ',
    actions: payload.urgencyTag === 'GUEST_HANDSHAKE_REQ'
      ? [
          { action: 'approve', title: 'Allow Entry' },
          { action: 'deny', title: 'Decline' },
        ]
      : [],
  };

  event.waitUntil(
    self.registration.showNotification(payload.title || 'Chronos Ledger', options)
  );
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();

  if (event.action === 'approve' || event.action === 'deny') {
    const url = event.notification.data?.url;
    if (url) event.waitUntil(clients.openWindow(url));
    return;
  }

  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        const target = event.notification.data?.url || '/';
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.postMessage({ type: 'NAVIGATE', url: target });
            return client.focus();
          }
        }
        return clients.openWindow(target);
      })
  );
});

// ── Background sync: flush offline attendance queue ──────────────────────────

self.addEventListener('sync', function (event) {
  if (event.tag === 'attendance-sync') {
    event.waitUntil(syncOfflineAttendance());
  }
});

async function syncOfflineAttendance() {
  try {
    const db = await openChronosDB();
    const tx = db.transaction('attendance-queue', 'readwrite');
    const store = tx.objectStore('attendance-queue');
    const records = await store.getAll();

    for (const record of records) {
      try {
        const response = await fetch('/api/v1/attendance/mark', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${record.token}` },
          body: JSON.stringify(record.payload),
        });
        // 2xx means marked; a 4xx is a final verdict (expired token,
        // deleted ledger) that a retry can never fix. Only network errors
        // and 5xx keep the record for the next sync.
        if (response.status < 500) await store.delete(record.id);
      } catch {
        // Keep the record — will retry on next sync
      }
    }
    await tx.done;
  } catch {
    // Silently fail — will retry on next sync event
  }
}

// ── Periodic background sync: local class start notifications ────────────────
// Fires even when the app is closed. Reads cached schedule from IndexedDB and
// shows a local notification for any class starting within 20 minutes.

self.addEventListener('periodicsync', function (event) {
  if (event.tag === 'class-reminder-check') {
    event.waitUntil(checkUpcomingClasses());
  }
});

async function checkUpcomingClasses() {
  try {
    const db = await openChronosDB();
    const scheduleTx = db.transaction('schedule-cache', 'readonly');
    const allSchedules = await scheduleTx.objectStore('schedule-cache').getAll();
    await scheduleTx.done;

    const now = Date.now();
    const today = new Date().toISOString().split('T')[0];
    const NOTIFY_WINDOW_MS = 20 * 60 * 1000; // notify if class starts within 20 min

    for (const scheduleRecord of allSchedules) {
      for (const entry of scheduleRecord.entries) {
        if (!entry.time_window_start || entry.operational_state === 'ON_LEAVE') continue;

        const [h, m] = entry.time_window_start.split(':').map(Number);
        const classStart = new Date();
        classStart.setHours(h, m, 0, 0);

        const msUntilClass = classStart.getTime() - now;
        if (msUntilClass < 0 || msUntilClass > NOTIFY_WINDOW_MS) continue;

        const notifKey = `${today}_${entry.id}`;
        const notifTx = db.transaction('notified-classes', 'readwrite');
        const notifStore = notifTx.objectStore('notified-classes');
        const alreadyNotified = await notifStore.get(notifKey);

        if (!alreadyNotified) {
          await self.registration.showNotification(`Class in ${Math.round(msUntilClass / 60000)} min: ${entry.course_code}`, {
            body: `${entry.course_title} · Room ${entry.target_room_identifier}`,
            icon: '/icons/icon-192x192.png',
            badge: '/icons/icon-72x72.png',
            tag: `class-remind-${entry.id}`,
            data: { url: '/member/dashboard?tab=attendance' },
          });
          await notifStore.put({ key: notifKey, notified_at: new Date().toISOString() });
        }
        await notifTx.done;
      }
    }
  } catch {
    // Silently fail — non-critical
  }
}

// ── Message handler: schedule updates from the page ─────────────────────────

self.addEventListener('message', function (event) {
  if (event.data?.type === 'SCHEDULE_UPDATE') {
    // Register periodic sync when the page hands us a fresh schedule
    if ('periodicSync' in self.registration) {
      self.registration.periodicSync
        .register('class-reminder-check', { minInterval: 10 * 60 * 1000 }) // every 10 min
        .catch(() => {}); // permission not granted — graceful degradation
    }
  }
});

// ── Minimal IDB helper (no library dependency in SW context) ─────────────────

function openChronosDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('chronos-offline', 2);
    req.onsuccess = () => resolve(wrapIDB(req.result));
    req.onerror = () => reject(req.error);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('attendance-queue')) {
        const s = db.createObjectStore('attendance-queue', { keyPath: 'id', autoIncrement: true });
        s.createIndex('by_date', 'queued_at');
      }
      if (!db.objectStoreNames.contains('schedule-cache')) {
        db.createObjectStore('schedule-cache', { keyPath: 'user_id' });
      }
      if (!db.objectStoreNames.contains('notified-classes')) {
        db.createObjectStore('notified-classes', { keyPath: 'key' });
      }
    };
  });
}

// Lightweight promise wrapper around IDBObjectStore operations
function wrapIDB(db) {
  return {
    transaction(storeNames, mode) {
      const tx = db.transaction(storeNames, mode);
      const stores = {};
      const storeArr = Array.isArray(storeNames) ? storeNames : [storeNames];
      storeArr.forEach((name) => {
        const store = tx.objectStore(name);
        stores[name] = {
          getAll: () => idbReq(store.getAll()),
          get: (key) => idbReq(store.get(key)),
          put: (val) => idbReq(store.put(val)),
          delete: (key) => idbReq(store.delete(key)),
        };
        Object.assign(stores, { [name]: stores[name] });
      });
      return Object.assign(stores, {
        done: new Promise((res, rej) => {
          tx.oncomplete = res;
          tx.onerror = () => rej(tx.error);
          tx.onabort = () => rej(tx.error);
        }),
        objectStore: (name) => stores[name],
      });
    },
  };
}

function idbReq(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
