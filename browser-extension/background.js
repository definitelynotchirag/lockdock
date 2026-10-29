// Reports the active tab of the focused window to the lockdock daemon.
const api = globalThis.browser ?? globalThis.chrome;
const DEFAULTS = { port: 47231, token: "" };
const DEBOUNCE_MS = 150;

function browserName() {
  const ua = navigator.userAgent;
  if (/Firefox\//.test(ua)) return /Zen\//.test(ua) ? "zen" : "firefox";
  if (/Helium/i.test(ua)) return "helium";
  if (/Edg\//.test(ua)) return "edge";
  if (/OPR\//.test(ua)) return "opera";
  if (/Vivaldi/.test(ua)) return "vivaldi";
  if (/Brave/i.test(ua) || globalThis.navigator?.brave) return "brave";
  if (/Chrome\//.test(ua)) return "chromium";
  return "browser";
}

let timer = null;

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(report, DEBOUNCE_MS);
}

async function report() {
  try {
    const [tab] = await api.tabs.query({ active: true, lastFocusedWindow: true });
    if (!tab || !tab.url) return;
    const { port, token } = await api.storage.sync.get(DEFAULTS);
    const headers = { "Content-Type": "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;
    await fetch(`http://127.0.0.1:${port}/url`, {
      method: "POST",
      headers,
      body: JSON.stringify({ url: tab.url, title: tab.title || "", browser: browserName() }),
    });
  } catch (_) {
    // daemon not running: stay quiet
  }
}

api.tabs.onActivated.addListener(schedule);
api.tabs.onUpdated.addListener((_id, change, tab) => {
  if ((change.url || change.title) && tab.active) schedule();
});
api.windows.onFocusChanged.addListener(schedule);
