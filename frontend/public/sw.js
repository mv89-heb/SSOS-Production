self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (_) {
    data = { title: "SSOS", body: event.data ? event.data.text() : "תזכורת חדשה" };
  }

  const title = data.title || "SSOS – תזכורת חדשה";
  const options = {
    body: data.body || "נוצרה תזכורת חדשה.",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    dir: "rtl",
    lang: "he",
    data: { url: data.url || "/dashboard", order_id: data.order_id || null },
    tag: data.type === "reminder_created" ? `reminder-created-${data.order_id || Date.now()}` : `reminder-${data.order_id || Date.now()}`,
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = event.notification.data && event.notification.data.url;
  if (!target) return;

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(target);
      return undefined;
    })
  );
});
