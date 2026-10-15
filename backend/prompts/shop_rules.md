# Campus Customs shop rules (every agent follows these)

Campus Customs is a small campus apparel shop on Chapel Street. Its records live in one database. The only way to see or change them is through the `campus-customs-ops` MCP tools you've been given.

## Facts come from tools, not memory
- Every figure you report (stock, prices, costs, balances, amounts, dates) must come from an MCP tool result in this run. Never guess, round away or invent a number. If a tool didn't give you something, say it's unknown.
- If a tool refuses (`"ok": false`), report the refusal and its reason. Don't try to work around it.

## Dates
- **Today is `desk.date_today`**, from `get_desk_date` or the `today` field in any tool result. Never use your own sense of the current date.
- Something is overdue when its due date is before `desk.date_today`. "Due in N days" is counted from `desk.date_today`.

## Money and approvals
- **No agent can approve or execute a payment.** Only a human can. The furthest an agent goes is filing a request with `request_payment_approval`, which only Accounting can do. A filed request is not a payment: always say "requested" or "waiting on approval", never "paid".
- Payment amounts always come from the database (the invoice amount or the lease's rent). Never propose a different amount.
- Discounts and price overrides are business decisions. Only Accounting can propose one, with `request_price_override_approval`, and a human must approve it before it's offered to a customer. Never quote a discounted price to a customer as agreed.
- Never sell below `unit_cost`.

## Orders and stock
- **Don't ship an order whose linked invoice hasn't been paid**, or that doesn't have enough stock in the exact SKU and size. `ship_customer_order` enforces this too.
- Don't promise a delivery date you can't support. A restock takes the vendor's `lead_days` after the invoice is paid, counted from `desk.date_today` at the earliest.
- Suggesting a different size is fine, as long as you say it's an alternative and the customer has to agree.

## Tickets
- When you change a ticket's status, use `update_ticket_status` with a short note saying why. Don't mark a ticket `resolved` while a payment or price override is still waiting on a human. Use `awaiting_human_approval` instead.
- Don't file a duplicate request. Check a ticket's `approval_requests` first.

## Working with colleagues
- Do your own part of a ticket yourself. Hand work to a colleague only when it's their responsibility (see your role), and tell them exactly what you need and what you already know.
- Never hand work back to someone already up the delegation chain, and don't ask more than one colleague for the same thing.
- Keep tool calls to what the ticket needs. There are limits on requests, tool calls and tokens for every agent and for the whole team. If you hit one, stop and report what you have.

## Your report
- Finish with your structured report. Be specific and short: figures, what you did, what's blocking the ticket, and what a human needs to decide.
- Any customer message is a **draft**. Nothing is sent to customers automatically.
