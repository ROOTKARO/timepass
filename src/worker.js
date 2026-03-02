export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/" && request.method === "GET") {
      return new Response("Bot running", { status: 200 });
    }

    // Telegram webhook on root
    if (url.pathname === "/" && request.method === "POST") {
      const update = await request.json();
      await onUpdate(update, env);
      return new Response("ok", { status: 200 });
    }

    return new Response("not found", { status: 404 });
  }
};

    // Accept both /webhook and /webhook/
    if (
      request.method === "POST" &&
      (url.pathname === "/webhook" || url.pathname === "/webhook/")
    ) {
      const update = await request.json();
      await onUpdate(update, env);
      return new Response("ok", { status: 200 });
    }

    return new Response("not found", { status: 404 });
  }
};

async function onUpdate(update, env) {
  const msg = update?.message;
  if (!msg?.text || !msg?.chat?.id) return;

  const chatId = msg.chat.id;
  const text = msg.text.trim();

  if (text === "/start") {
    return send(
      env,
      chatId,
      "Thanks For Choosing RELAX TOOL -\n/search market_model=RMX5210 project_no=22667\n/search rmx5210 22667"
    );
  }

  if (!text.toLowerCase().startsWith("/search")) {
    return send(env, chatId, "Use /search");
  }

  const rows = await loadRows(env);
  const query = text.replace(/^\/search\s*/i, "").toLowerCase().trim();

  if (!query) {
    return send(env, chatId, "Usage: /search market_model=... project_no=...");
  }

  const tokens = query.split(/\s+/).filter(Boolean);
  const f = {};
  const free = [];

  for (const t of tokens) {
    const i = t.indexOf("=");
    if (i > 0) {
      const k = t.slice(0, i);
      const v = t.slice(i + 1);
      if (["market_model", "project_no", "filename"].includes(k)) f[k] = v;
    } else {
      free.push(t);
    }
  }

  const hits = rows.filter((r) => {
    const mm = String(r.market_model || "").toLowerCase();
    const pn = String(r.project_no || "").toLowerCase();
    const fn = String(r.filename || "").toLowerCase();

    if (f.market_model && !mm.includes(f.market_model)) return false;
    if (f.project_no && !pn.includes(f.project_no)) return false;
    if (f.filename && !fn.includes(f.filename)) return false;

    const hay = `${mm} ${pn} ${fn}`;
    return free.every((x) => hay.includes(x));
  });

  if (!hits.length) return send(env, chatId, "No match found.");

  const out = hits
    .slice(0, 20)
    .map(
      (r, i) =>
        `${i + 1}) ${r.market_model} | ${r.project_no} | ${r.filename}\n${r.link || ""}`
    )
    .join("\n\n");

  return send(env, chatId, out);
}

async function loadRows(env) {
  const res = await fetch(env.DATA_URL, { cf: { cacheTtl: 300, cacheEverything: true } });
  const raw = await res.json();

  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw.realmeLinks)) return raw.realmeLinks;
  for (const v of Object.values(raw || {})) {
    if (Array.isArray(v)) return v;
  }
  return [];
}

async function send(env, chatId, text) {
  await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text })
  });
}

