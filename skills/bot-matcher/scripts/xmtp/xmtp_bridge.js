#!/usr/bin/env node
/**
 * ClawMatch XMTP Bridge — local HTTP ↔ XMTP relay.
 *
 * Connects to the XMTP network using an Ethereum private key,
 * listens for incoming XMTP messages, and exposes a local HTTP API
 * so Python scripts can send/receive messages without Node.js deps.
 *
 * Env vars:
 *   XMTP_PRIVATE_KEY  — hex private key (from wallet.json)
 *   XMTP_ENV          — "dev" | "production" | "local" (default: "dev")
 *   BRIDGE_PORT       — local HTTP port (default: 3500)
 *
 * Local API (localhost only):
 *   POST /send         — send XMTP message {to, content}
 *   GET  /inbox        — get buffered incoming messages [?since=ISO&clear=1]
 *   GET  /health       — bridge status {connected, address, env, inbox_count}
 *   POST /clear-inbox  — clear the inbox buffer
 */

import { createSigner, createUser, getInboxIdForAddress } from "@xmtp/node-sdk";
import { createWalletClient, http, toBytes } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { sepolia } from "viem/chains";
import express from "express";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PRIVATE_KEY = process.env.XMTP_PRIVATE_KEY;
const XMTP_ENV = process.env.XMTP_ENV || "dev";
const BRIDGE_PORT = parseInt(process.env.BRIDGE_PORT || "3500", 10);

if (!PRIVATE_KEY) {
  console.error("ERROR: XMTP_PRIVATE_KEY env var is required (hex private key from wallet.json)");
  process.exit(1);
}

// ---------------------------------------------------------------------------
// In-memory inbox buffer
// ---------------------------------------------------------------------------
const inbox = [];
const MAX_INBOX = 5000;

function addToInbox(msg) {
  inbox.push(msg);
  if (inbox.length > MAX_INBOX) inbox.shift();
}

// ---------------------------------------------------------------------------
// XMTP Client Setup
// ---------------------------------------------------------------------------
let xmtpClient = null;
let walletAddress = "";

async function initXmtp() {
  const key = PRIVATE_KEY.startsWith("0x") ? PRIVATE_KEY : `0x${PRIVATE_KEY}`;
  const account = privateKeyToAccount(key);
  walletAddress = account.address.toLowerCase();

  console.log(`[XMTP] Wallet: ${walletAddress}`);
  console.log(`[XMTP] Environment: ${XMTP_ENV}`);

  // Create signer from private key
  const encryptionKey = crypto.getRandomValues(new Uint8Array(32));
  const signer = createSigner(key);
  const user = createUser(key);

  // Import the Client dynamically
  const { Client } = await import("@xmtp/node-sdk");

  // Create XMTP client
  xmtpClient = await Client.create(user, encryptionKey, {
    env: XMTP_ENV,
  });

  console.log(`[XMTP] Connected! Inbox ID: ${xmtpClient.inboxId}`);

  // Start listening for messages in background
  streamMessages();

  return xmtpClient;
}

// ---------------------------------------------------------------------------
// Message Streaming (background)
// ---------------------------------------------------------------------------
async function streamMessages() {
  try {
    // Sync conversations first
    await xmtpClient.conversations.sync();

    const stream = xmtpClient.conversations.streamAllMessages();

    for await (const message of stream) {
      // Skip our own messages
      if (message.senderInboxId === xmtpClient.inboxId) continue;

      const entry = {
        id: message.id,
        senderInboxId: message.senderInboxId,
        conversationId: message.conversationId,
        content: message.content,
        sentAt: message.sentAt?.toISOString() || new Date().toISOString(),
        receivedAt: new Date().toISOString(),
      };

      addToInbox(entry);
      console.log(`[XMTP] Message from ${message.senderInboxId.slice(0, 12)}...`);
    }
  } catch (err) {
    console.error("[XMTP] Stream error:", err.message);
    // Retry after delay
    setTimeout(streamMessages, 5000);
  }
}

// ---------------------------------------------------------------------------
// Express HTTP API (localhost only)
// ---------------------------------------------------------------------------
const app = express();
app.use(express.json({ limit: "1mb" }));

// Health check
app.get("/health", (_req, res) => {
  res.json({
    status: xmtpClient ? "connected" : "disconnecting",
    address: walletAddress,
    inboxId: xmtpClient?.inboxId || null,
    env: XMTP_ENV,
    inbox_count: inbox.length,
    uptime: process.uptime(),
  });
});

// Send message via XMTP
app.post("/send", async (req, res) => {
  try {
    const { to, content } = req.body;
    if (!to || !content) {
      return res.status(400).json({ error: "missing 'to' (wallet address) or 'content'" });
    }

    const targetAddress = to.toLowerCase();

    // Check if the target can receive XMTP messages
    const canMessage = await xmtpClient.canMessage([targetAddress]);
    if (!canMessage.get(targetAddress)) {
      return res.status(404).json({
        error: `Address ${targetAddress} is not reachable on XMTP (${XMTP_ENV}). They need to start their bridge first.`,
      });
    }

    // Sync conversations
    await xmtpClient.conversations.sync();

    // Create or get DM conversation
    const conversation = await xmtpClient.conversations.newDm(targetAddress);
    await conversation.sync();

    // Send message (serialize as JSON string if content is object)
    const messageText = typeof content === "string" ? content : JSON.stringify(content);
    const msgId = await conversation.send(messageText);

    res.json({
      status: "sent",
      messageId: msgId,
      to: targetAddress,
      conversationId: conversation.id,
    });
  } catch (err) {
    console.error("[XMTP] Send error:", err.message);
    res.status(500).json({ error: err.message });
  }
});

// Get inbox messages
app.get("/inbox", (req, res) => {
  const since = req.query.since ? new Date(req.query.since) : null;
  const clear = req.query.clear === "1" || req.query.clear === "true";

  let messages = inbox;
  if (since) {
    messages = inbox.filter((m) => new Date(m.receivedAt) > since);
  }

  const result = { messages: [...messages], count: messages.length };

  if (clear) {
    inbox.length = 0;
  }

  res.json(result);
});

// Clear inbox
app.post("/clear-inbox", (_req, res) => {
  const count = inbox.length;
  inbox.length = 0;
  res.json({ cleared: count });
});

// Resolve: check if an address can receive XMTP messages
app.get("/can-message", async (req, res) => {
  try {
    const address = req.query.address?.toLowerCase();
    if (!address) {
      return res.status(400).json({ error: "missing 'address' query param" });
    }
    const canMessage = await xmtpClient.canMessage([address]);
    res.json({ address, canMessage: canMessage.get(address) || false });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
async function main() {
  try {
    await initXmtp();

    app.listen(BRIDGE_PORT, "127.0.0.1", () => {
      console.log(`[Bridge] HTTP API listening on http://127.0.0.1:${BRIDGE_PORT}`);
      console.log(`[Bridge] Ready — send messages via POST /send, read via GET /inbox`);
    });
  } catch (err) {
    console.error("[Bridge] Fatal:", err);
    process.exit(1);
  }
}

main();
