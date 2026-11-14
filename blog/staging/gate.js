/* Sign-in gate for the blog review pages (review, nothing-pending, pipeline health).
   Same Supabase login as the toolkit and Robert's other apps; access is the app 'blog-review' on access.imetrobert.com
   (public.has_app_access('blog-review')). Fails CLOSED: until the session is verified the page content stays hidden.
   Honest limit: this is a browser-side gate on a static site. It keeps the interface and its buttons away from anyone
   without a login, but a staged draft's own file can still be fetched by someone who guesses its exact address.
   Loaded synchronously in <head> of each page, after the inline "awr-gated" class snippet. */
(function () {
  "use strict";
  var AUTH = { url: "https://ipnajvgwtjrlecbqfwrh.supabase.co", key: "sb_publishable_oPa7fZdSTeXKuCwpOF338Q_PcXS57go",
               app: "blog-review", storageKey: "awr_blogreview_auth" };
  var GRACE_MS = 24 * 3600 * 1000;   // offline: trust a session that was verified within a day

  function load() { try { return JSON.parse(localStorage.getItem(AUTH.storageKey) || "null"); } catch (e) { return null; } }
  function save(v) { try { localStorage.setItem(AUTH.storageKey, JSON.stringify(v)); } catch (e) {} }
  function clear() { try { localStorage.removeItem(AUTH.storageKey); } catch (e) {} }
  function api(path, body, token) {
    var c = new AbortController(), to = setTimeout(function () { c.abort(); }, 12000);
    var headers = { apikey: AUTH.key, "Content-Type": "application/json" };
    if (token) headers.Authorization = "Bearer " + token;
    return fetch(AUTH.url + path, { method: "POST", body: JSON.stringify(body), signal: c.signal, headers: headers })
      .then(function (r) { return r.json().catch(function () { return null; }).then(function (j) { clearTimeout(to); return { ok: r.ok, status: r.status, json: j }; }); })
      .catch(function (e) { clearTimeout(to); throw e; });
  }
  function hasAccess(token) {
    return api("/rest/v1/rpc/has_app_access", { app_name: AUTH.app }, token).then(function (r) {
      if (r.ok) return r.json === true;
      return r.status === 401 ? "expired" : "error";
    });
  }
  function mk(j, email, verified) {
    return { access: j.access_token, refresh: j.refresh_token, expires: Date.now() + (j.expires_in || 3600) * 1000, email: email || (j.user && j.user.email) || "", verified: verified };
  }
  function signIn(email, pw) {
    return api("/auth/v1/token?grant_type=password", { email: email, password: pw }).then(function (r) {
      if (!r.ok) return r.status >= 500 ? "error" : "wrong";
      return hasAccess(r.json.access_token).then(function (ok) {
        if (ok !== true) return ok === false ? "noaccess" : "error";
        save(mk(r.json, email, Date.now())); return "ok";
      });
    }).catch(function () { return "offline"; });
  }
  function verify() {
    var s = load(); if (!s) return Promise.resolve("revoked");
    function refresh() {
      return api("/auth/v1/token?grant_type=refresh_token", { refresh_token: s.refresh }).then(function (r) {
        if (!r.ok) return r.status >= 500 ? "error" : "revoked";
        var n = mk(r.json, s.email, s.verified); s.access = n.access; s.refresh = n.refresh; s.expires = n.expires; return "ok";
      });
    }
    var step = s.expires < Date.now() + 60000 ? refresh() : Promise.resolve("ok");
    return step.then(function (x) {
      if (x !== "ok") { if (x === "revoked") clear(); return x; }
      return hasAccess(s.access).then(function (ok) {
        if (ok === "expired") return refresh().then(function (y) { if (y !== "ok") { if (y === "revoked") clear(); return y; } return hasAccess(s.access).then(finish); });
        return finish(ok);
      });
    }).catch(function () {
      return (s.verified && Date.now() - s.verified < GRACE_MS) ? "ok" : "offline";
    });
    function finish(ok) {
      if (ok === true) { s.verified = Date.now(); save(s); return "ok"; }
      if (ok === false) { clear(); return "noaccess"; }
      return "error";
    }
  }

  var MSG = {
    wrong: "That email or password is not right.",
    noaccess: "This account does not have access to the blog review pages. Ask for access on access.imetrobert.com.",
    offline: "Could not reach the sign-in service. Check your connection and try again.",
    revoked: "Please sign in.",
    error: "Something went wrong signing in. Try again in a minute."
  };

  function open() { document.documentElement.classList.remove("awr-gated"); var g = document.getElementById("awr-gate"); if (g) g.remove(); addSignOut(); }
  function addSignOut() {
    if (document.getElementById("awr-signout")) return;
    var b = document.createElement("button"); b.id = "awr-signout"; b.type = "button"; b.textContent = "Sign out";
    b.style.cssText = "position:fixed;right:10px;bottom:10px;z-index:2147483000;font:600 12px system-ui;padding:6px 10px;border-radius:8px;border:1px solid #94a3b8;background:#fff;color:#1e293b;opacity:.85";
    b.onclick = function () { clear(); location.reload(); };
    document.body.appendChild(b);
  }
  function show(msg) {
    var g = document.getElementById("awr-gate");
    if (!g) {
      g = document.createElement("div"); g.id = "awr-gate";
      g.style.cssText = "position:fixed;inset:0;z-index:2147483001;background:#0f172a;display:flex;align-items:center;justify-content:center;padding:1rem;visibility:visible";
      g.innerHTML = '<form style="background:#fff;border-radius:14px;padding:1.4rem;max-width:340px;width:100%;font:15px system-ui;color:#1e293b">' +
        '<h1 style="font-size:1.1rem;margin:0 0 .3rem">Blog review</h1><p style="margin:0 0 .9rem;color:#64748b;font-size:.85rem">Sign in with your usual AI with Robert login.</p>' +
        '<input id="awr-e" type="email" autocomplete="username" autocapitalize="off" autocorrect="off" placeholder="Email" style="width:100%;padding:.6rem;margin-bottom:.5rem;border:1px solid #cbd5e1;border-radius:8px;font-size:16px">' +
        '<input id="awr-p" type="password" autocomplete="current-password" placeholder="Password" style="width:100%;padding:.6rem;margin-bottom:.6rem;border:1px solid #cbd5e1;border-radius:8px;font-size:16px">' +
        '<button id="awr-go" type="submit" style="width:100%;padding:.65rem;border:0;border-radius:10px;background:#2563eb;color:#fff;font:600 15px system-ui">Sign in</button>' +
        '<p id="awr-m" role="status" style="margin:.7rem 0 0;color:#b91c1c;font-size:.85rem;min-height:1.2em"></p></form>';
      document.body.appendChild(g);
      g.querySelector("form").onsubmit = function (ev) {
        ev.preventDefault();
        var e = g.querySelector("#awr-e").value.trim(), p = g.querySelector("#awr-p").value;
        if (!e || !p) return;
        var go = g.querySelector("#awr-go"); go.disabled = true; go.textContent = "Signing in...";
        signIn(e, p).then(function (r) {
          if (r === "ok") { open(); return; }
          go.disabled = false; go.textContent = "Sign in"; g.querySelector("#awr-m").textContent = MSG[r] || MSG.error;
        });
      };
    }
    if (msg) g.querySelector("#awr-m").textContent = MSG[msg] || "";
  }

  function start() {
    var s = load();
    if (!s) { show(); return; }
    verify().then(function (r) { if (r === "ok") open(); else show(r === "revoked" ? "" : r); });
  }
  document.documentElement.classList.add("awr-gated");
  var st = document.createElement("style");
  st.textContent = "html.awr-gated body>*:not(#awr-gate){visibility:hidden!important}";
  document.head.appendChild(st);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
