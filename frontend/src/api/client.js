const BASE = "/api/v1";

function headers(merchantId, idempotencyKey = null) {
  const h = {
    "Content-Type": "application/json",
    "X-Merchant-Id": merchantId,
  };
  if (idempotencyKey) h["Idempotency-Key"] = idempotencyKey;
  return h;
}

function uuidv4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export async function fetchBalance(merchantId) {
  const res = await fetch(`${BASE}/balance`, {
    headers: headers(merchantId),
  });
  if (!res.ok) throw new Error(`Balance fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchPayouts(merchantId) {
  const res = await fetch(`${BASE}/payouts`, {
    headers: headers(merchantId),
  });
  if (!res.ok) throw new Error(`Payout list failed: ${res.status}`);
  return res.json();
}

export async function createPayout(merchantId, amountPaise, bankAccountId) {
  const res = await fetch(`${BASE}/payouts`, {
    method: "POST",
    headers: headers(merchantId, uuidv4()),
    body: JSON.stringify({
      amount_paise: amountPaise,
      bank_account_id: bankAccountId,
    }),
  });
  const data = await res.json();
  if (!res.ok) throw Object.assign(new Error(data.detail || data.error || "Request failed"), { data });
  return data;
}

export async function fetchLedger(merchantId) {
  const res = await fetch(`${BASE}/ledger`, {
    headers: headers(merchantId),
  });
  if (!res.ok) throw new Error(`Ledger fetch failed: ${res.status}`);
  return res.json();
}

export async function addCredit(merchantId, amountPaise) {
  const res = await fetch(`${BASE}/credits`, {
    method: "POST",
    headers: headers(merchantId),
    body: JSON.stringify({ amount_paise: amountPaise }),
  });
  if (!res.ok) throw new Error("Credit failed");
  return res.json();
}
