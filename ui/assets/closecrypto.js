/* Сквозное шифрование «Близких» — тот же формат, что core/closecrypto.py (описание — там): X25519, seal = поток
   HMAC-SHA256 + тег HMAC-SHA256, ключ сообщения завёрнут для каждого устройства. Без WebCrypto: SHA-256 и X25519 —
   свои, синхронные (WebCrypto асинхронный и бывает недоступен в WebView), чтобы телефон и компьютер считали одинаково.
   window.DewiarCrypto: keypair, x25519, seal, unseal, encryptFor, decryptFrom, b64e, b64d, utf8, fromUtf8, randomBytes;
   hmacKey(key) -> (сообщение -> HMAC) — подготовленный ключ, для многих сообщений (PBKDF2 сейфа, safe.js). */
(function (root) {
  "use strict";
  // ---------- SHA-256 и HMAC ----------
  const K = new Uint32Array([0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb,
    0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f,
    0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);
  const IV = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const W = new Uint32Array(64);
  function compress(st, b, o) {                   // st — Uint32Array(8), блок 64 байта из b начиная с o
    for (let i = 0; i < 16; i++) W[i] = (b[o + 4 * i] << 24) | (b[o + 4 * i + 1] << 16) | (b[o + 4 * i + 2] << 8) | b[o + 4 * i + 3];
    for (let i = 16; i < 64; i++) {
      const x = W[i - 15], y = W[i - 2];
      const s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3);
      const s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) | 0;
    }
    let a = st[0], bb = st[1], c = st[2], d = st[3], e = st[4], f = st[5], g = st[6], h = st[7];
    for (let i = 0; i < 64; i++) {
      const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const t1 = (h + S1 + ((e & f) ^ (~e & g)) + K[i] + W[i]) | 0;
      const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const t2 = (S0 + ((a & bb) ^ (a & c) ^ (bb & c))) | 0;
      h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = bb; bb = a; a = (t1 + t2) | 0;
    }
    st[0] = (st[0] + a) | 0; st[1] = (st[1] + bb) | 0; st[2] = (st[2] + c) | 0; st[3] = (st[3] + d) | 0;
    st[4] = (st[4] + e) | 0; st[5] = (st[5] + f) | 0; st[6] = (st[6] + g) | 0; st[7] = (st[7] + h) | 0;
  }
  // хэш с готового состояния st (уже обработано pre байт) для сообщения m -> 32 байта
  function finish(st0, pre, m) {
    const st = new Uint32Array(st0), n = m.length, total = pre + n;
    let i = 0;
    for (; i + 64 <= n; i += 64) compress(st, m, i);
    const tail = new Uint8Array(((n - i + 9 + 63) >> 6) << 6);
    tail.set(m.subarray(i)); tail[n - i] = 0x80;
    const bits = total * 8, L = tail.length;
    tail[L - 4] = (bits >>> 24) & 255; tail[L - 3] = (bits >>> 16) & 255; tail[L - 2] = (bits >>> 8) & 255; tail[L - 1] = bits & 255;
    tail[L - 5] = Math.floor(bits / 4294967296) & 255;
    for (let j = 0; j < L; j += 64) compress(st, tail, j);
    const out = new Uint8Array(32);
    for (let j = 0; j < 8; j++) { out[4 * j] = st[j] >>> 24; out[4 * j + 1] = (st[j] >>> 16) & 255; out[4 * j + 2] = (st[j] >>> 8) & 255; out[4 * j + 3] = st[j] & 255; }
    return out;
  }
  const sha256 = (m) => finish(new Uint32Array(IV), 0, m);
  function hmacKey(key) {                         // подготовленные внутреннее и внешнее состояния — быстро для многих сообщений
    if (key.length > 64) key = sha256(key);
    const ip = new Uint8Array(64), op = new Uint8Array(64);
    for (let i = 0; i < 64; i++) { ip[i] = (key[i] || 0) ^ 0x36; op[i] = (key[i] || 0) ^ 0x5c; }
    const si = new Uint32Array(IV), so = new Uint32Array(IV); compress(si, ip, 0); compress(so, op, 0);
    return (m) => finish(so, 64, finish(si, 64, m));
  }
  const hmac = (key, m) => hmacKey(key)(m);

  // ---------- X25519 (RFC 7748), BigInt ----------
  const P = (1n << 255n) - 19n, A24 = 121665n;
  const md = (x) => { x %= P; return x < 0n ? x + P : x; };
  function pw(b, e) { let r = 1n; b = md(b); while (e > 0n) { if (e & 1n) r = r * b % P; b = b * b % P; e >>= 1n; } return r; }
  const le2n = (b) => { let n = 0n; for (let i = b.length - 1; i >= 0; i--) n = (n << 8n) | BigInt(b[i]); return n; };
  const n2le = (n) => { const o = new Uint8Array(32); for (let i = 0; i < 32; i++) { o[i] = Number(n & 255n); n >>= 8n; } return o; };
  function x25519(k, u) {
    if (k.length !== 32 || u.length !== 32) throw new Error("ключ X25519 — 32 байта");
    const kb = Uint8Array.from(k); kb[0] &= 248; kb[31] &= 127; kb[31] |= 64;
    const n = le2n(kb), x1 = le2n(u) & ((1n << 255n) - 1n);
    let x2 = 1n, z2 = 0n, x3 = x1, z3 = 1n, swap = 0n;
    for (let t = 254n; t >= 0n; t--) {
      const kt = (n >> t) & 1n; swap ^= kt;
      if (swap) { [x2, x3] = [x3, x2]; [z2, z3] = [z3, z2]; }
      swap = kt;
      const a = md(x2 + z2), aa = a * a % P, b = md(x2 - z2), bb = b * b % P, e = md(aa - bb);
      const c = md(x3 + z3), d = md(x3 - z3), da = d * a % P, cb = c * b % P;
      x3 = md((da + cb) * (da + cb)); z3 = md(x1 * md((da - cb) * (da - cb)));
      x2 = aa * bb % P; z2 = md(e * md(aa + A24 * e));
    }
    if (swap) { [x2, x3] = [x3, x2]; [z2, z3] = [z3, z2]; }
    return n2le(x2 * pw(z2, P - 2n) % P);
  }
  const BASE = (() => { const b = new Uint8Array(32); b[0] = 9; return b; })();

  // ---------- байты, base64url, UTF-8 ----------
  function randomBytes(n) {                       // getRandomValues — не больше 64 КБ за раз
    const b = new Uint8Array(n), c = root.crypto || globalThis.crypto;
    for (let i = 0; i < n; i += 65536) c.getRandomValues(b.subarray(i, Math.min(n, i + 65536)));
    return b;
  }
  function b64e(b) { let s = ""; for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000)); return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
  function b64d(s) { s = String(s || "").replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; const t = atob(s), o = new Uint8Array(t.length); for (let i = 0; i < t.length; i++) o[i] = t.charCodeAt(i); return o; }
  const utf8 = (s) => new TextEncoder().encode(String(s));
  const fromUtf8 = (b) => new TextDecoder().decode(b);
  const cat = (...a) => { const o = new Uint8Array(a.reduce((n, x) => n + x.length, 0)); let p = 0; a.forEach(x => { o.set(x, p); p += x.length; }); return o; };

  // ---------- seal / unseal ----------
  function stream(kenc, nonce, n) {
    const H = hmacKey(kenc), out = new Uint8Array(Math.ceil(n / 32) * 32), m = new Uint8Array(20); m.set(nonce);
    for (let i = 0, o = 0; o < n; i++, o += 32) { m[16] = i >>> 24; m[17] = (i >>> 16) & 255; m[18] = (i >>> 8) & 255; m[19] = i & 255; out.set(H(m), o); }
    return out;
  }
  function seal(key, data, nonce) {
    if (key.length !== 32) throw new Error("ключ — 32 байта");
    nonce = nonce || randomBytes(16);
    const kenc = hmac(key, utf8("dewiar-enc")), kmac = hmac(key, utf8("dewiar-mac")), ks = stream(kenc, nonce, data.length);
    const ct = new Uint8Array(data.length); for (let i = 0; i < data.length; i++) ct[i] = data[i] ^ ks[i];
    return cat(nonce, ct, hmac(kmac, cat(nonce, ct)));
  }
  function unseal(key, blob) {
    if (key.length !== 32 || blob.length < 48) throw new Error("повреждённые данные");
    const nonce = blob.subarray(0, 16), ct = blob.subarray(16, blob.length - 32), tag = blob.subarray(blob.length - 32);
    const kenc = hmac(key, utf8("dewiar-enc")), kmac = hmac(key, utf8("dewiar-mac")), want = hmac(kmac, cat(nonce, ct));
    let diff = 0; for (let i = 0; i < 32; i++) diff |= want[i] ^ tag[i];
    if (diff) throw new Error("не сходится подпись — данные изменены или ключ не тот");
    const ks = stream(kenc, nonce, ct.length), out = new Uint8Array(ct.length);
    for (let i = 0; i < ct.length; i++) out[i] = ct[i] ^ ks[i];
    return out;
  }
  function wrapKey(priv, pub, from, to) {
    const s = x25519(priv, pub); if (!s.some(x => x)) throw new Error("плохой открытый ключ");
    return hmac(s, utf8(`dewiar-close-v1|${from}|${to}`));
  }
  function keypair() { const priv = randomBytes(32); return { priv, pub: x25519(priv, BASE) }; }
  function encryptFor(payload, priv, myDev, targets) {    // targets — {устройство: открытый ключ (Uint8Array)}
    const k = randomBytes(32), keys = {};
    for (const [d, pub] of Object.entries(targets)) keys[d] = b64e(seal(wrapKey(priv, pub, myDev, d), k));
    return { v: 1, fd: myDev, k: keys, c: b64e(seal(k, utf8(JSON.stringify(payload)))) };
  }
  function decryptFrom(env, priv, myDev, senderPub) {
    if ((+env.v || 0) !== 1) throw new Error("сообщение новой версии — обновите Dewiar");
    const w = (env.k || {})[myDev]; if (!w) throw new Error("сообщение не для этого устройства");
    const k = unseal(wrapKey(priv, senderPub, env.fd || "", myDev), b64d(w));
    return JSON.parse(fromUtf8(unseal(k, b64d(env.c || ""))));
  }
  root.DewiarCrypto = { sha256, hmac, hmacKey, x25519, keypair, seal, unseal, wrapKey, encryptFor, decryptFrom, b64e, b64d, utf8, fromUtf8, randomBytes, BASE };
})(typeof window !== "undefined" ? window : globalThis);
