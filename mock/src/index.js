// Placeholder: the bank's services are written here from the final case's service contract and test customers.
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/health") return Response.json({ ok: true });
    return Response.json({ ok: false, error: "not implemented yet" }, { status: 404 });
  },
};
