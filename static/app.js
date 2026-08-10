const state = { username: "", token: "", contact: "", socket: null, contactPrekeyId: "" };
const KEY_PREFIX = "encryptochat.demo.keys.";
const encoder = new TextEncoder();

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function addMessage(text, mine = false) {
  const el = document.createElement("div");
  el.className = mine ? "message mine" : "message";
  el.textContent = text;
  document.querySelector("#messages").appendChild(el);
  el.scrollIntoView({ block: "end" });
}

function addStatus(text) {
  const el = document.createElement("p");
  el.className = "status-item";
  el.textContent = text;
  document.querySelector("#statusList").prepend(el);
}

function bytesToBase64(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function usernameKey(username) {
  return `${KEY_PREFIX}${username.toLowerCase()}`;
}

async function createKeyMaterial() {
  const encryption = await crypto.subtle.generateKey({ name: "X25519" }, true, ["deriveBits"]);
  const signing = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  return {
    encryptionPrivate: await crypto.subtle.exportKey("jwk", encryption.privateKey),
    encryptionPublic: bytesToBase64(new Uint8Array(await crypto.subtle.exportKey("raw", encryption.publicKey))),
    signingPrivate: await crypto.subtle.exportKey("jwk", signing.privateKey),
    signingPublic: bytesToBase64(new Uint8Array(await crypto.subtle.exportKey("raw", signing.publicKey))),
    prekeys: {},
  };
}

function loadKeyMaterial(username) {
  const stored = localStorage.getItem(usernameKey(username));
  return stored ? JSON.parse(stored) : null;
}

function saveKeyMaterial(username, keys) {
  localStorage.setItem(usernameKey(username), JSON.stringify(keys));
}

async function login(username, keys) {
  const challenge = await api(`/auth/challenge/${encodeURIComponent(username)}`);
  const signingKey = await crypto.subtle.importKey("jwk", keys.signingPrivate, { name: "Ed25519" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("Ed25519", signingKey, encoder.encode(challenge.challenge));
  const result = await api("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, challenge: challenge.challenge, signature: bytesToBase64(new Uint8Array(signature)) }),
  });
  state.token = result.access_token;
}

async function registerOrLogin() {
  const username = document.querySelector("#username").value.trim().toLowerCase();
  if (!username) throw new Error("Enter a username.");
  if (!window.crypto?.subtle) throw new Error("This browser does not support Web Crypto.");

  let keys = loadKeyMaterial(username);
  if (!keys) {
    keys = await createKeyMaterial();
    saveKeyMaterial(username, keys);
  }

  try {
    await api("/register", {
      method: "POST",
      body: JSON.stringify({ username, public_key: keys.encryptionPublic, signing_public_key: keys.signingPublic }),
    });
    addStatus(`Registered ${username}.`);
  } catch (error) {
    if (!String(error.message).includes("Username already exists")) throw error;
    addStatus(`Using existing account ${username}.`);
  }

  await login(username, keys);
  state.username = username;
  document.querySelector("#authState").textContent = `Signed in as ${username}`;
  document.querySelector("#fingerprint").textContent = `Key fingerprint: ${keys.encryptionPublic.slice(0, 16)}`;
  connectSocket();
  await refreshPrekeyHealth();
  await loadInbox();
  addStatus("API and WebSocket demo shell connected. Messages are demo envelopes.");
}

async function generatePrekeys(count = 5) {
  const keys = loadKeyMaterial(state.username);
  const prekeys = [];
  for (let index = 0; index < count; index += 1) {
    const pair = await crypto.subtle.generateKey({ name: "X25519" }, true, ["deriveBits"]);
    const id = crypto.randomUUID().replaceAll("-", "");
    keys.prekeys[id] = await crypto.subtle.exportKey("jwk", pair.privateKey);
    prekeys.push({ id, key: bytesToBase64(new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey))) });
  }
  saveKeyMaterial(state.username, keys);
  return prekeys;
}

async function refreshPrekeyHealth() {
  if (!state.username) return;
  const health = await api(`/users/${encodeURIComponent(state.username)}/prekeys/count`);
  document.querySelector("#prekeyHealth").textContent = `Unused prekeys: ${health.count}${health.low ? " (low)" : ""}`;
}

async function refillPrekeys() {
  if (!state.username) throw new Error("Register or log in first.");
  const prekeys = await generatePrekeys();
  const result = await api(`/users/${encodeURIComponent(state.username)}/prekeys`, {
    method: "POST",
    body: JSON.stringify({ prekeys }),
  });
  await refreshPrekeyHealth();
  addStatus(`Uploaded prekeys. ${result.count} unused keys available.`);
}

async function openContact() {
  if (!state.username) throw new Error("Register or log in first.");
  const contact = document.querySelector("#contactName").value.trim().toLowerCase();
  if (!contact) throw new Error("Enter a contact username.");
  const keys = await api(`/users/${encodeURIComponent(contact)}/keys`);
  state.contact = keys.username;
  state.contactPrekeyId = keys.prekey.id;
  document.querySelector("#activeContact").textContent = `Chat with ${keys.username}`;
  addStatus(`Opened ${keys.username} with prekey ${keys.prekey.id.slice(0, 8)}.`);
}

function demoCiphertext(text) {
  return bytesToBase64(encoder.encode(`DEMO:${new Date().toISOString()}:${text}`));
}

async function sendMessage(event) {
  event.preventDefault();
  if (!state.contact || !state.contactPrekeyId) throw new Error("Open a contact with an available prekey first.");
  const input = document.querySelector("#messageText");
  const text = input.value.trim();
  if (!text) return;
  const result = await api("/send", {
    method: "POST",
    body: JSON.stringify({
      to: state.contact,
      frm: state.username,
      ciphertext: demoCiphertext(text),
      prekey_id: state.contactPrekeyId,
    }),
  });
  addMessage(`Sent demo envelope: ${text}`, true);
  input.value = "";
  state.contactPrekeyId = "";
  addStatus(`Message ${result.message_id} sent. Open the contact again for another prekey.`);
}

async function handleIncoming(envelope) {
  addMessage(`Encrypted envelope from ${envelope.from}: ${envelope.ciphertext}`);
  if (envelope.id) await api(`/messages/${envelope.id}/read`, { method: "POST" });
  addStatus(`Message ${envelope.id} marked read.`);
}

async function loadInbox() {
  const inbox = await api(`/inbox/${encodeURIComponent(state.username)}`);
  for (const envelope of inbox.inbox) await handleIncoming(envelope);
}

function connectSocket() {
  if (state.socket) state.socket.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  state.socket = new WebSocket(`${scheme}://${location.host}/ws/${encodeURIComponent(state.username)}?token=${encodeURIComponent(state.token)}`);
  state.socket.onmessage = ({ data }) => handleIncoming(JSON.parse(data)).catch(reportError);
  state.socket.onopen = () => addStatus("WebSocket connected.");
  state.socket.onclose = () => addStatus("WebSocket disconnected.");
}

function reportError(error) {
  addStatus(`Error: ${error.message || error}`);
}

document.querySelector("#registerBtn").addEventListener("click", () => registerOrLogin().catch(reportError));
document.querySelector("#addContactBtn").addEventListener("click", () => openContact().catch(reportError));
document.querySelector("#refillPrekeysBtn").addEventListener("click", () => refillPrekeys().catch(reportError));
document.querySelector("#composer").addEventListener("submit", (event) => sendMessage(event).catch(reportError));
