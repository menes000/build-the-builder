// Freya Bank statement-debt services, test environment mock (service contract 2026-10-01, section 6).
// Every answer comes from test-customers.json: the stored HTTP status and body, exactly. A customer, card or week that is
// not in the file gets the contract's 404 for that service, or a 400 INVALID_ARGUMENTS_ERROR where the service has no 404.
import DATA from "./test-customers.json";

const BASE = "/voice/v1/";
const CORS = { "Access-Control-Allow-Origin": "*" };

// lookup tables built once per isolate
const BY_CUSTOMER = new Map();          // customerNo -> customer
const BY_CARD = new Map();              // masked cardNumber -> customer
for (const c of DATA.customers) {
  BY_CUSTOMER.set(String(c.customerNo).trim(), c);
  for (const svc of ["cards.balance", "statement.week.get", "statement.week.decide", "statement.week.change"]) {
    for (const card of Object.keys(c.services[svc] || {})) BY_CARD.set(card, c);
  }
}
const FIRST = DATA.customers[0];

// service -> required data fields, how to look up, and the not-found answer
const SERVICES = {
  "cards.list": { required: ["customerNo"], key: "customer", notFound: [404, "FB_IVR_CHANNEL_102", "WARNING", "Müşteriye ait geçerli kart bilgisi bulunamadı."] },
  "cards.balance": { required: ["cardNumber"], key: "card", notFound: [404, "FB_IVR_CHANNEL_120", "WARNING", "Kart bakiye servisi hatası: kart bulunamadı"] },
  "statement.week.get": { required: ["cardNumber"], key: "card", notFound: [404, "FB_IVR_CHANNEL_121", "WARNING", "Kart bulunamadı"] },
  "statement.week.decide": { required: ["cardNumber", "newStatementWeek", "statementDay"], key: "card+week", notFound: null },
  "statement.week.change": { required: ["cardNumber", "newStatementWeek", "statementDay"], key: "card+week", notFound: null },
  "contact.email.get": { required: ["customerNo", "intAddressInfoType"], key: "customer", notFound: null },
  "statement.pdf.send": { required: ["customerNo", "cardNumber", "currencyType", "statementDate", "emailAddress"], key: "customer", notFound: [404, "FB_IVR_CHANNEL_107", "WARNING", "Pdf dokümanı bulunamadı"] },
};

function guid() {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" } });
}

function errorBody(code, type, message, rootCause) {
  const g = guid();
  return { result: { guid: g, returnCode: code, messageText: message, code, message, type,
    details: { guid: g, rootCause, errorOrigin: "ivr-gateway-test:ivr-channel-v0" } } };
}

function invalid(field) {
  const label = field === "cardNumber" ? "card number" : field;
  return json(errorBody("INVALID_ARGUMENTS_ERROR", "ERROR", `${label} cannot be empty`, "InvalidArgumentsException"), 400);
}

function notFound(svc) {
  const nf = SERVICES[svc].notFound;
  if (!nf) return json(errorBody("INVALID_ARGUMENTS_ERROR", "ERROR", "no test record for this request", "InvalidArgumentsException"), 400);
  const [status, code, type, message] = nf;
  return json(errorBody(code, type, message, "NotFoundException"), status);
}

// The panel's "Test API Request" button sends variables unfilled, e.g. "{{customerNumber}}".
function isTemplate(v) {
  return typeof v === "string" && (v.startsWith("{{") || v.startsWith("%7B%7B"));
}

function empty(v) {
  return v === undefined || v === null || (typeof v === "string" && v.trim() === "");
}

async function serve(stored) {
  if (!stored || typeof stored !== "object" || !("http" in stored)) return null;
  if (stored.delaySeconds) await new Promise((r) => setTimeout(r, Number(stored.delaySeconds) * 1000));
  return json(stored.response, stored.http);
}

async function handle(svc, body) {
  const spec = SERVICES[svc];
  const data = (body && typeof body.data === "object" && body.data) || {};
  for (const f of spec.required) {
    if (empty(data[f])) return invalid(f);
  }
  let customer;
  let entry = null;
  if (spec.key === "customer") {
    customer = isTemplate(data.customerNo) ? FIRST : BY_CUSTOMER.get(String(data.customerNo).trim());
    entry = customer && customer.services[svc];
  } else {
    let card = String(data.cardNumber).trim();
    if (isTemplate(data.cardNumber)) card = Object.keys(FIRST.services[svc] || {})[0] || card;
    customer = BY_CARD.get(card);
    const perCard = customer && (customer.services[svc] || {})[card];
    if (spec.key === "card") entry = perCard;
    else entry = perCard && perCard[isTemplate(data.newStatementWeek) ? Object.keys(perCard)[0] : String(data.newStatementWeek).trim()];
  }
  return (await serve(entry)) || notFound(svc);
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: { ...CORS, "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "*" } });
    }
    const path = url.pathname.replace(/\/+$/, "");
    if (request.method === "GET" && (path === "/health" || path === "")) return json({ ok: true, services: Object.keys(SERVICES).map((s) => "POST " + BASE + s) });
    if (path.startsWith(BASE)) {
      const svc = path.slice(BASE.length);
      if (SERVICES[svc]) {
        if (request.method !== "POST") return json(errorBody("INVALID_ARGUMENTS_ERROR", "ERROR", "use POST", "InvalidArgumentsException"), 400);
        let body = null;
        try { body = await request.json(); } catch { body = null; }
        try {
          return await handle(svc, body);
        } catch (e) {
          return json(errorBody("FBE00099", "ERROR", "Teknik hata: ABORTED: ", "TechnicalError"), 500);
        }
      }
    }
    return json(errorBody("INVALID_ARGUMENTS_ERROR", "ERROR", "unknown path", "InvalidArgumentsException"), 404);
  },
};
