"""Concierge agent: takes over the chores after a donor uploads an item.

A LangGraph agent loop (docs/05). The concierge model (Modal, tool calling)
decides which specialist to call next; each tool goes through the orchestrator,
which owns the DB:

    get_price_quote     -> pricing agent (Modal) + eBay comps
    check_local_demand  -> matchmaker agent (open requests, pgvector)
    list_for_sale       -> Shopstr listing; unsold 30 days -> donation pool
    donate_item         -> donation + matchmaker offers it to waiting requests

Offline (no Modal) or if the model fails, a rule policy plays the concierge
in the same graph, so the flow, the feed, and the tests are identical.
"""
import json
import time
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agents import orchestrator
from app.agents.events import current_run, emit
from app.core import config, llm
from app.schemas import HandleOut

MAX_STEPS = 12          # LangGraph recursion limit: about 5 tool rounds
DONATE_BELOW = 15       # USD: under this, selling isn't worth the donor's time

SYSTEM_PROMPT = f"""You are Rehome's concierge. A donor uploaded an item and wants it gone
without any more work. You do the work with your tools.
1. Call get_price_quote and check_local_demand.
2. Decide. Respect the donor's preference if it is "sell" or "donate". Otherwise:
   donate if someone nearby is waiting for this kind of item, or if it is worth
   under ${DONATE_BELOW}; else sell it.
3. Call exactly one of list_for_sale (price within the quoted range) or donate_item.
4. Reply to the donor in 2-3 plain sentences: what you did and why. If you listed
   it, say it moves to the donation pool if unsold after 30 days."""


class _Run:
    """What the tools learn during one run; also guards against acting twice."""
    def __init__(self, draft_id: str, preference: str):
        self.draft_id, self.preference = draft_id, preference
        self.item = orchestrator.draft_item(draft_id)      # 404 FlowError if missing
        self.quote = None          # SellOut
        self.demand: list[dict] | None = None
        self.action: str | None = None
        self.result = None         # ListItemOut or DonateOut
        self.brain = "modal" if _model_configured() else "rules"
        self.steps: list[str] = []


def _model_configured() -> bool:
    return not config.USE_STUBS and bool(config.MODAL_AGENT_MODEL)


def _model(tools):
    """The concierge's brain: the Modal tool-calling model (infra/modal_llm.py)."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=config.MODAL_AGENT_MODEL, base_url=config.MODAL_ENDPOINT_URL,
                      api_key=config.MODAL_API_KEY or "not-needed", temperature=0.2,
                      timeout=180, max_retries=1, max_tokens=4096,
                      extra_body=llm.modal_extra_body() or None
                      ).bind_tools(tools, tool_choice="required")   # act, don't chat


# ---- tools (each one is a specialist agent behind the orchestrator) ----------
def _tools(run: _Run) -> list:
    @tool
    async def get_price_quote() -> str:
        """Ask the pricing agent what the donor's item would sell for (eBay comps)."""
        t = _start(run, "get_price_quote", "→ pricing: what would this sell for?")
        run.quote = await orchestrator.sell_draft(run.draft_id)
        p = run.quote.suggested_price
        return _done(run, "get_price_quote", t, "pricing",
                     f"${p.low:g}–{p.high:g} ({run.quote.basis})",
                     {"low": p.low, "high": p.high, "basis": run.quote.basis,
                      "comps": len(run.quote.comps),
                      "listing_title": run.quote.listing_draft.title})

    @tool
    async def check_local_demand() -> str:
        """Ask the matchmaker agent whether anyone nearby has an open request for this item."""
        t = _start(run, "check_local_demand", "→ matchmaker: is anyone nearby waiting for this?")
        run.demand = await orchestrator.local_demand(run.item)
        n = len(run.demand)
        return _done(run, "check_local_demand", t, "matchmaker",
                     f"{n} waiting request{'s' * (n != 1)}",
                     {"waiting_requests": n, "needs": [", ".join(d["needs"]) for d in run.demand],
                      "request_ids": [d["request_id"] for d in run.demand]})

    @tool
    async def list_for_sale(price: float) -> str:
        """List the item for sale on Shopstr at `price` USD. Unsold after 30 days, it
        moves to the donation pool automatically."""
        return await _act(run, "listed", price)

    @tool
    async def donate_item() -> str:
        """Donate the item: it becomes searchable and is offered to waiting requests."""
        return await _act(run, "donated")

    return [get_price_quote, check_local_demand, list_for_sale, donate_item]


def _start(run: _Run, tool_name: str, ask: str) -> float:
    """Log the request to a specialist; returns the start time for _done."""
    run.steps.append(tool_name)
    emit("concierge", ask, tool=tool_name)
    return time.perf_counter()


def _done(run: _Run, tool_name: str, started: float, agent: str, summary: str,
          result: dict) -> str:
    """Log the specialist's answer (tool, latency, result) and hand it to the model."""
    ms = round((time.perf_counter() - started) * 1000)
    emit(agent, f"← {summary} ({ms} ms)", tool=tool_name, duration_ms=ms, data=result)
    return json.dumps(result)


async def _act(run: _Run, action: str, price: float | None = None) -> str:
    name = "list_for_sale" if action == "listed" else "donate_item"
    if run.action:
        emit("concierge", f"Refused a second action ({name}): already {run.action}", tool=name)
        return f"Already done: the item was {run.action}. Now reply to the donor."
    run.action = action           # set before awaiting, so parallel calls can't both act
    p = run.quote.suggested_price if run.quote else None
    emit("concierge", f"Decided ({run.brain}): {'sell for $%g' % price if price else action}",
         data={"decision": name, "brain": run.brain, "price": price,
               "preference": run.preference, "waiting_requests": len(run.demand or []),
               "quote": {"low": p.low, "high": p.high} if p else None})
    try:
        if action == "listed":
            t = _start(run, name, f"→ marketplace: list it on Shopstr for ${price:g}")
            run.result = await orchestrator.post_draft(run.draft_id, price)
            return _done(run, name, t, "concierge",
                         f"listed {run.result.item.id} for ${run.result.listing.price:g}",
                         {"listed": True, "item_id": run.result.item.id,
                          "price": run.result.listing.price, "url": run.result.listing.url,
                          "dry_run": run.result.listing.dry_run})
        t = _start(run, name, "→ donation: make it searchable and offer it to waiting requests")
        run.result = await orchestrator.donate_draft(run.draft_id)
        return _done(run, name, t, "concierge", f"donated {run.result.item_id}",
                     {"donated": True, "item_id": run.result.item_id,
                      "offered_to": run.result.waiting_requests})
    except orchestrator.FlowError as e:
        run.action = None
        emit("concierge", f"Tool error ({name}): {e.detail}", tool=name,
             data={"error": e.detail, "status": e.status_code})
        return f"Error: {e.detail}"


# ---- rule policy: plays the concierge offline or when the model fails --------
def _decide(run: _Run) -> tuple[str, float | None]:
    p = run.quote.suggested_price
    if run.preference == "donate":
        return "donate_item", None
    if run.preference == "sell":
        return "list_for_sale", round((p.low + p.high) / 2)
    if run.demand or p.high < DONATE_BELOW:
        return "donate_item", None
    return "list_for_sale", round((p.low + p.high) / 2)


def _call(name: str, args: dict | None = None) -> dict:
    return {"name": name, "args": args or {}, "id": f"rule_{name}", "type": "tool_call"}


def _rule_step(run: _Run) -> AIMessage:
    if run.quote is None or run.demand is None:
        return AIMessage("", tool_calls=[_call("get_price_quote"), _call("check_local_demand")])
    if run.action is None:
        name, price = _decide(run)
        return AIMessage("", tool_calls=[_call(name, {"price": price} if price else None)])
    return AIMessage(_summary(run))


def _summary(run: _Run) -> str:
    what = run.item["item"]
    quote = ""
    if run.quote:
        p = run.quote.suggested_price
        label = "similar items are listed for" if run.quote.basis == "active listings" \
            else "I estimate it's worth"
        quote = f"{label} ${p.low:g}–{p.high:g}"
    if run.action == "listed":
        return (f"I priced your {what} ({quote}) and listed it on Shopstr for "
                f"${run.result.listing.price:g}. If it hasn't sold in 30 days, I'll move it "
                "to the donation pool so someone nearby can have it.")
    waiting = run.result.waiting_requests
    if waiting:
        why = (f"{len(waiting)} {'person' if len(waiting) == 1 else 'people'} nearby "
               f"{'is' if len(waiting) == 1 else 'are'} already looking for one")
    elif run.preference == "donate":
        why = "you asked to donate it"
    else:
        why = f"{quote}, so it isn't worth the hassle of selling" if quote else "it's quicker"
    tail = " and offered it to them" if waiting else "; it's now searchable for people nearby"
    return f"I donated your {what} because {why}{tail}."


# ---- the graph ---------------------------------------------------------------
def _graph(run: _Run):
    tools = _tools(run)

    async def concierge(state: MessagesState):
        if run.action:   # done: the summary comes from what the tools did (no extra model call)
            return {"messages": [AIMessage(_summary(run))]}
        if run.brain == "modal":
            try:
                return {"messages": [await _model(tools).ainvoke(state["messages"])]}
            except Exception as e:   # model down or bad reply: rules take over mid-run
                emit("concierge", f"Model unavailable ({type(e).__name__}); switching to rules")
                run.brain = "rules"
        return {"messages": [_rule_step(run)]}

    g = StateGraph(MessagesState)
    g.add_node("concierge", concierge)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "concierge")
    g.add_conditional_edges("concierge", tools_condition)   # tool calls -> tools, else end
    g.add_edge("tools", "concierge")
    return g.compile()


async def handle(draft_id: str, preference: str = "auto") -> HandleOut:
    """Run the concierge on a draft until it is listed or donated. Every event
    in the run (its own, and those of the agents it calls) shares one run_id."""
    run = _Run(draft_id, preference)
    token = current_run.set(f"run_{uuid.uuid4().hex[:10]}")
    try:
        return await _handle(run)
    finally:
        current_run.reset(token)


async def _handle(run: _Run) -> HandleOut:
    draft_id, preference = run.draft_id, run.preference
    started = time.perf_counter()
    emit("concierge", f"Taking over {draft_id} ({run.item['item']}): price it, check "
         "local demand, then sell or donate",
         data={"draft_id": draft_id, "preference": preference, "brain": run.brain,
               "model": config.MODAL_AGENT_MODEL if run.brain == "modal" else None})
    messages = [SystemMessage(SYSTEM_PROMPT),
                HumanMessage(json.dumps({"item": run.item, "donor_preference": preference}))]
    final = ""
    try:
        out = await _graph(run).ainvoke({"messages": messages},
                                        {"recursion_limit": MAX_STEPS})
        final = out["messages"][-1].content if run.action else ""
    except GraphRecursionError:
        emit("concierge", "Too many steps; finishing with rules")

    if run.action is None:   # the model stopped without acting: never leave the item in limbo
        if run.brain == "modal":
            emit("concierge", "The model didn't decide; finishing with rules")
        run.brain = "rules"
        tools = {t.name: t for t in _tools(run)}
        if run.quote is None:
            await tools["get_price_quote"].ainvoke({})
        if run.demand is None:
            await tools["check_local_demand"].ainvoke({})
        name, price = _decide(run)
        result = await tools[name].ainvoke({"price": price} if price else {})
        if run.action is None:
            raise orchestrator.FlowError(502, f"The concierge couldn't finish: {result}")

    summary = final.strip() if isinstance(final, str) and final.strip() else _summary(run)
    listed = run.action == "listed"
    item_id = run.result.item.id if listed else run.result.item_id
    ms = round((time.perf_counter() - started) * 1000)
    emit("concierge", summary, item_id=item_id, duration_ms=ms,
         data={"action": run.action, "brain": run.brain, "steps": run.steps})
    return HandleOut(
        run_id=current_run.get(), draft_id=draft_id, action=run.action, summary=summary,
        brain=run.brain,
        steps=run.steps, item_id=item_id,
        price_quote=run.quote.suggested_price if run.quote else None,
        waiting_requests=[] if listed else run.result.waiting_requests,
        listing=run.result.listing if listed else None)
