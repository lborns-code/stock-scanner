"""
דף הגדרות — מריץ שרת מקומי לעדכון config.json בקלות.
הרץ: python settings_server.py
"""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CONFIG_PATH = Path("config.json")
PORT = 5050


def load_cfg():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_cfg(cfg: dict):
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress console noise

    def do_GET(self):
        if self.path == "/" or self.path == "/settings":
            cfg = load_cfg()
            html = build_html(cfg)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/api/config":
            cfg = load_cfg()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(cfg, ensure_ascii=False).encode())

        elif self.path == "/stop":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Stopping...")
            import threading
            threading.Thread(target=self.server.shutdown).start()

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
            cfg = load_cfg()

            action = data.get("action", "")

            if action == "save_positions":
                positions = data.get("positions", {})
                cfg["positions"] = positions
                save_cfg(cfg)
                self._ok({"status": "saved", "msg": "פוזיציות נשמרו ✅"})

            elif action == "save_watchlist":
                tickers = [t.strip().upper() for t in data.get("tickers", []) if t.strip()]
                cfg["watchlist"] = tickers
                # sync positions keys
                for t in tickers:
                    cfg.setdefault("positions", {}).setdefault(t, {"shares": 0, "avg_cost": 0, "invested_usd": 0})
                save_cfg(cfg)
                self._ok({"status": "saved", "msg": "Watchlist עודכן ✅"})

            elif action == "save_settings":
                cfg["investor_profile"]["total_capital_usd"] = float(data.get("total_capital", cfg["investor_profile"]["total_capital_usd"]))
                cfg["investor_profile"]["position_size_max"] = float(data.get("position_max", cfg["investor_profile"]["position_size_max"]))
                if data.get("api_key") and data["api_key"] != "***":
                    cfg["anthropic_api_key"] = data["api_key"]
                save_cfg(cfg)
                self._ok({"status": "saved", "msg": "הגדרות נשמרו ✅"})

            elif action == "save_telegram":
                cfg.setdefault("telegram", {})
                cfg["telegram"]["bot_token"] = data.get("bot_token", "")
                cfg["telegram"]["chat_id"] = data.get("chat_id", "")
                cfg["telegram"]["enabled"] = bool(data.get("bot_token") and data.get("chat_id"))
                save_cfg(cfg)
                self._ok({"status": "saved", "msg": "טלגרם נשמר ✅"})

            else:
                self._ok({"status": "error", "msg": "פעולה לא מוכרת"})

        except Exception as e:
            self._ok({"status": "error", "msg": str(e)})

    def _ok(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode())


def build_html(cfg: dict) -> str:
    positions = cfg.get("positions", {})
    watchlist = cfg.get("watchlist", [])
    profile = cfg.get("investor_profile", {})
    tg = cfg.get("telegram", {})

    # build positions rows
    pos_rows = ""
    for ticker in watchlist:
        p = positions.get(ticker, {"shares": 0, "avg_cost": 0, "invested_usd": 0})
        shares = p.get("shares", 0)
        avg_cost = p.get("avg_cost", 0)
        invested = p.get("invested_usd", 0) or round(shares * avg_cost, 2)
        pos_rows += f"""
        <tr data-ticker="{ticker}">
          <td><strong style="color:#58a6ff">{ticker}</strong></td>
          <td><input type="number" step="0.001" min="0" class="inp shares" value="{shares}" placeholder="0"/></td>
          <td><input type="number" step="0.01" min="0" class="inp avg-cost" value="{avg_cost}" placeholder="0.00"/></td>
          <td><span class="calc-invested">${invested:.2f}</span></td>
        </tr>"""

    watchlist_str = ", ".join(watchlist)
    api_masked = "***" if cfg.get("anthropic_api_key", "").startswith("sk-") else cfg.get("anthropic_api_key", "")

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Scanner — הגדרות</title>
<style>
  :root {{
    --bg:#0d1117;--surface:#161b22;--surface2:#21262d;
    --border:#30363d;--text:#e6edf3;--muted:#8b949e;
    --green:#3fb950;--blue:#58a6ff;--red:#f85149;--amber:#d29922;
  }}
  * {{ box-sizing:border-box;margin:0;padding:0 }}
  body {{ background:var(--bg);color:var(--text);font-family:'Segoe UI',Arial,sans-serif;font-size:14px;padding:20px }}
  .container {{ max-width:900px;margin:0 auto }}
  h1 {{ font-size:22px;margin-bottom:4px }}
  h1 span {{ color:var(--blue) }}
  .subtitle {{ color:var(--muted);font-size:13px;margin-bottom:24px }}
  .card {{ background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px }}
  .card h2 {{ font-size:15px;font-weight:700;margin-bottom:16px;color:var(--blue) }}
  table {{ width:100%;border-collapse:collapse }}
  th {{ color:var(--muted);font-size:11px;text-align:right;padding:6px 10px;border-bottom:1px solid var(--border) }}
  td {{ padding:8px 10px;border-bottom:1px solid rgba(48,54,61,0.5) }}
  .inp {{ background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:6px 10px;color:var(--text);font-size:13px;width:100%;max-width:120px }}
  .inp:focus {{ outline:none;border-color:var(--blue) }}
  .btn {{ background:var(--blue);color:#000;border:none;border-radius:8px;padding:10px 24px;font-size:14px;font-weight:700;cursor:pointer;margin-top:12px }}
  .btn:hover {{ opacity:0.85 }}
  .btn-red {{ background:var(--red);color:#fff }}
  .toast {{ position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#238636;color:#fff;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;display:none;z-index:999 }}
  .field-row {{ display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap }}
  .field-row label {{ color:var(--muted);font-size:12px;min-width:140px }}
  .field-row input {{ background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text);font-size:13px;flex:1;min-width:200px }}
  .field-row input:focus {{ outline:none;border-color:var(--blue) }}
  .tag {{ display:inline-block;background:rgba(88,166,255,0.15);color:var(--blue);border:1px solid var(--blue);border-radius:20px;padding:3px 10px;font-size:12px;margin:2px }}
  .status-dot {{ width:8px;height:8px;border-radius:50%;display:inline-block;margin-left:6px }}
  .dot-green {{ background:var(--green) }}
  .dot-red {{ background:var(--red) }}
  .nav {{ display:flex;gap:8px;margin-bottom:20px }}
  .nav a {{ color:var(--muted);text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;border:1px solid var(--border) }}
  .nav a:hover {{ color:var(--blue);border-color:var(--blue) }}
</style>
</head>
<body>
<div class="container">
  <h1>📊 <span>Stock Scanner</span> — הגדרות</h1>
  <p class="subtitle">עדכן את הפוזיציות, הגדרות והמניות שלך</p>

  <div class="nav">
    <a href="/settings">⚙️ הגדרות</a>
    <a href="/stop">🛑 סגור שרת</a>
  </div>

  <!-- POSITIONS -->
  <div class="card">
    <h2>💼 הפוזיציות שלי — P&L מעקב</h2>
    <p style="color:var(--muted);font-size:12px;margin-bottom:12px">הכנס כמות מניות ועלות ממוצעת — הדוח יחשב רווח/הפסד אוטומטית</p>
    <table>
      <thead><tr><th>מניה</th><th>כמות מניות</th><th>עלות ממוצעת $</th><th>סה"כ הושקע</th></tr></thead>
      <tbody id="pos-tbody">{pos_rows}</tbody>
    </table>
    <button class="btn" onclick="savePositions()">💾 שמור פוזיציות</button>
  </div>

  <!-- WATCHLIST -->
  <div class="card">
    <h2>👀 Watchlist — מניות לעקוב</h2>
    <p style="color:var(--muted);font-size:12px;margin-bottom:12px">מניות שתמיד יופיעו בדוח (הפורטפוליו שלך)</p>
    <div style="margin-bottom:12px" id="tags-container">
      {" ".join(f'<span class="tag">{t} <span onclick="removeTicker(this)" style="cursor:pointer;opacity:0.6">✕</span></span>' for t in watchlist)}
    </div>
    <div class="field-row">
      <label>הוסף מניה:</label>
      <input id="new-ticker" type="text" placeholder="AAPL, TSLA, ..." style="max-width:200px" onkeydown="if(event.key==='Enter')addTicker()"/>
      <button class="btn" style="margin:0" onclick="addTicker()">+ הוסף</button>
    </div>
    <button class="btn" onclick="saveWatchlist()">💾 שמור Watchlist</button>
  </div>

  <!-- GENERAL SETTINGS -->
  <div class="card">
    <h2>⚙️ הגדרות כלליות</h2>
    <div class="field-row">
      <label>הון כולל ($):</label>
      <input id="total-capital" type="number" value="{profile.get('total_capital_usd', 1100)}"/>
    </div>
    <div class="field-row">
      <label>גודל פוזיציה מקס ($):</label>
      <input id="position-max" type="number" value="{profile.get('position_size_max', 300)}"/>
    </div>
    <div class="field-row">
      <label>Anthropic API Key:</label>
      <input id="api-key" type="password" value="{api_masked}" placeholder="sk-ant-..."/>
    </div>
    <button class="btn" onclick="saveSettings()">💾 שמור הגדרות</button>
  </div>

  <!-- TELEGRAM -->
  <div class="card">
    <h2>📱 טלגרם
      <span class="status-dot {'dot-green' if tg.get('enabled') else 'dot-red'}"></span>
      <span style="font-size:12px;color:var(--muted)">{'מופעל' if tg.get('enabled') else 'כבוי'}</span>
    </h2>
    <div class="field-row">
      <label>Bot Token:</label>
      <input id="tg-token" type="password" value="{tg.get('bot_token','')}" placeholder="1234567890:ABC..."/>
    </div>
    <div class="field-row">
      <label>Chat ID:</label>
      <input id="tg-chat" type="text" value="{tg.get('chat_id','')}" placeholder="123456789"/>
    </div>
    <button class="btn" onclick="saveTelegram()">💾 שמור טלגרם</button>
    <button class="btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);margin-right:8px" onclick="testTelegram()">🧪 בדוק שליחה</button>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
function showToast(msg, color='#238636') {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = color;
  t.style.display = 'block';
  setTimeout(() => t.style.display='none', 3000);
}}

// Auto-calculate invested when shares/avg-cost change
document.querySelectorAll('#pos-tbody tr').forEach(row => {{
  const sharesInp = row.querySelector('.shares');
  const costInp = row.querySelector('.avg-cost');
  const calcSpan = row.querySelector('.calc-invested');
  function update() {{
    const s = parseFloat(sharesInp.value) || 0;
    const c = parseFloat(costInp.value) || 0;
    calcSpan.textContent = '$' + (s*c).toFixed(2);
  }}
  sharesInp.addEventListener('input', update);
  costInp.addEventListener('input', update);
}});

function savePositions() {{
  const positions = {{}};
  document.querySelectorAll('#pos-tbody tr').forEach(row => {{
    const ticker = row.dataset.ticker;
    const shares = parseFloat(row.querySelector('.shares').value) || 0;
    const avg_cost = parseFloat(row.querySelector('.avg-cost').value) || 0;
    positions[ticker] = {{ shares, avg_cost, invested_usd: parseFloat((shares*avg_cost).toFixed(2)) }};
  }});
  post({{action:'save_positions', positions}});
}}

const currentTickers = {json.dumps(watchlist)};
function getTickers() {{
  return Array.from(document.querySelectorAll('#tags-container .tag')).map(el => el.textContent.replace('✕','').trim());
}}
function addTicker() {{
  const inp = document.getElementById('new-ticker');
  const t = inp.value.trim().toUpperCase();
  if (!t) return;
  const container = document.getElementById('tags-container');
  const span = document.createElement('span');
  span.className = 'tag';
  span.innerHTML = t + ' <span onclick="removeTicker(this)" style="cursor:pointer;opacity:0.6">✕</span>';
  container.appendChild(span);
  inp.value = '';
}}
function removeTicker(el) {{ el.parentElement.remove(); }}
function saveWatchlist() {{ post({{action:'save_watchlist', tickers: getTickers()}}); }}

function saveSettings() {{
  post({{
    action:'save_settings',
    total_capital: document.getElementById('total-capital').value,
    position_max: document.getElementById('position-max').value,
    api_key: document.getElementById('api-key').value,
  }});
}}

function saveTelegram() {{
  post({{
    action:'save_telegram',
    bot_token: document.getElementById('tg-token').value,
    chat_id: document.getElementById('tg-chat').value,
  }});
}}

function testTelegram() {{
  const token = document.getElementById('tg-token').value;
  const chat = document.getElementById('tg-chat').value;
  if (!token || !chat) {{ showToast('הכנס token ו-chat_id קודם', '#f85149'); return; }}
  fetch(`https://api.telegram.org/bot${{token}}/sendMessage`, {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{chat_id: chat, text:'✅ Stock Scanner מחובר! הגדרות תקינות.'}})
  }}).then(r=>r.json()).then(d=>{{
    if(d.ok) showToast('✅ הודעת טסט נשלחה!');
    else showToast('❌ שגיאה: ' + d.description, '#f85149');
  }}).catch(()=>showToast('❌ שגיאת רשת', '#f85149'));
}}

function post(data) {{
  fetch('/api/save', {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify(data)
  }}).then(r=>r.json()).then(d=>showToast(d.msg || 'נשמר ✅')).catch(e=>showToast('שגיאה: '+e, '#f85149'));
}}
</script>
</body>
</html>"""


if __name__ == "__main__":
    # fix POST route
    Handler.do_POST.__doc__ = "handle /api/save"

    # patch route to /api/save
    original_post = Handler.do_POST

    def patched_post(self):
        if self.path == "/api/save":
            original_post(self)
        else:
            self.send_response(404)
            self.end_headers()

    Handler.do_POST = patched_post

    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}/settings"
    print(f"\n✅ דף הגדרות פתוח ב: {url}")
    print("   לסגירה: לחץ Ctrl+C\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 שרת נסגר")
