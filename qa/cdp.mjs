// Мінімальний драйвер CDP: відкриває сторінку й виконує в ній JS.
const BASE = process.env.CDP || 'http://127.0.0.1:9222';

async function open(url){
  const r = await fetch(`${BASE}/json/new?${encodeURIComponent(url)}`, {method:'PUT'});
  return r.json();
}
export async function withPage(url, fn){
  const t = await open(url);
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  let id = 0; const waiting = new Map();
  await new Promise(res => ws.onopen = res);
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); }
  };
  const send = (method, params={}) => new Promise(res => {
    const mid = ++id; waiting.set(mid, res);
    ws.send(JSON.stringify({id: mid, method, params}));
  });
  const evaluate = async expr => {
    const r = await send('Runtime.evaluate',
      {expression: expr, awaitPromise: true, returnByValue: true});
    if (r.result?.exceptionDetails) throw new Error(
      r.result.exceptionDetails.exception?.description || 'JS error');
    return r.result?.result?.value;
  };
  // Знімок сторінки з ТОГО САМОГО сеансу: інакше режим із localStorage
  // (десктоп/мобільний) не переживає запуск окремого браузера.
  const shot = async (file, height) => {
    const fs = await import('node:fs');
    if (height) {
      await send('Emulation.setDeviceMetricsOverride',
        {width: 1200, height, deviceScaleFactor: 1, mobile: false});
      await sleep(600);   // дати сторінці перемалюватись після зміни розміру
    }
    const r = await send('Page.captureScreenshot', {format: 'png'});
    fs.writeFileSync(file, Buffer.from(r.result.data, 'base64'));
    return file;
  };
  // Розмір вікна для сторінки: без нього CDP дає ~766px, і медіазапити
  // вважають, що це вузький екран.
  const emulate = async (width = 1400, height = 900) => {
    await send('Emulation.setDeviceMetricsOverride',
      {width, height, deviceScaleFactor: 1, mobile: false});
    await sleep(400);
  };
  try { await fn(evaluate, shot, emulate); }
  finally { ws.close(); await fetch(`${BASE}/json/close/${t.id}`); }
}
export const sleep = ms => new Promise(r => setTimeout(r, ms));
