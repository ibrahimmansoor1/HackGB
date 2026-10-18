"""Concierge agent (LangGraph): POST /api/items/{draft_id}/handle.
Rule brain offline; the Modal brain is faked with scripted tool calls."""
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.agents import concierge
from app.core import config
from app.integrations import marketplace
from app.main import app

client = TestClient(app)
JACKET = "Black puffer jacket, hooded, water-resistant, size M"   # good condition: $15–23
CHICAGO = {"text": "need a warm coat, moving to Chicago in December", "zip": "60601"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "MARKETPLACE_DRY_RUN", True)
    monkeypatch.setattr(config, "NOSTR_NSEC", "")

    def no_network():
        raise AssertionError("tests must never open a real relay connection")
    monkeypatch.setattr(marketplace, "_new_client", no_network)


def _handle(text=JACKET, **body):
    draft_id = client.post("/api/items/parse", data={"zip": "54311", "text": text}).json()["draft_id"]
    return client.post(f"/api/items/{draft_id}/handle", json=body)


def _concierge_messages():
    return [e["message"] for e in client.get("/api/events").json()["events"]
            if e["agent"] == "concierge"]


# ---- rule brain (offline) ------------------------------------------------------
def test_worth_selling_and_nobody_waiting_gets_listed():
    r = _handle()
    assert r.status_code == 200
    out = r.json()
    assert out["brain"] == "rules" and out["action"] == "listed"
    assert out["steps"] == ["get_price_quote", "check_local_demand", "list_for_sale"]
    assert out["price_quote"] == {"low": 15, "high": 23, "currency": "USD"}
    assert out["listing"]["price"] == 19 and out["listing"]["dry_run"] is True
    assert "listed it on Shopstr for $19" in out["summary"] and "30 days" in out["summary"]
    [item] = client.get("/api/items?status=listed").json()["items"]
    assert item["id"] == out["item_id"]
    msgs = _concierge_messages()
    assert msgs[0].startswith("Taking over drf_") and msgs[-1] == out["summary"]
    assert "→ pricing: what would this sell for?" in msgs
    assert "→ matchmaker: is anyone nearby waiting for this?" in msgs


def test_run_is_traced_in_the_events_table():
    client.post("/api/requests", json={"text": "a unicorn costume", "zip": "54311"})  # other run
    out = _handle().json()
    assert out["run_id"].startswith("run_")
    trail = client.get(f"/api/events?run_id={out['run_id']}").json()["events"]
    assert trail and all(e["run_id"] == out["run_id"] for e in trail)
    agents = {e["agent"] for e in trail}
    assert {"concierge", "pricing", "matchmaker"} <= agents   # specialists share the run_id
    assert not any(e["message"].startswith("New request") for e in trail)

    answers = {e["tool"]: e for e in trail if e["tool"] and e["duration_ms"] is not None}
    assert set(answers) == {"get_price_quote", "check_local_demand", "list_for_sale"}
    assert answers["get_price_quote"]["data"] == {"low": 15, "high": 23, "basis": "estimate",
                                                 "comps": 0, "listing_title":
                                                 "Black Puffer Jacket, Size M, Good"}
    assert answers["list_for_sale"]["data"]["price"] == 19
    decided = next(e for e in trail if e["message"].startswith("Decided"))
    assert decided["data"]["decision"] == "list_for_sale" and decided["data"]["brain"] == "rules"
    last = trail[-1]
    assert last["message"] == out["summary"] and last["data"]["steps"] == out["steps"]
    assert last["duration_ms"] >= 0 and last["item_id"] == out["item_id"]

    other = client.get("/api/events").json()["events"]
    assert any(e["run_id"] is None for e in other)            # non-agent events stay untagged


def test_someone_waiting_means_donate_and_offer_it():
    req = client.post("/api/requests", json=CHICAGO).json()
    out = _handle().json()
    assert out["action"] == "donated" and out["waiting_requests"] == [req["request_id"]]
    assert "1 person nearby is already looking for one" in out["summary"]
    r = client.post("/api/matches/accept", json={"request_id": req["request_id"],
                                                 "item_id": out["item_id"]})
    assert r.status_code == 200


def test_cheap_item_is_donated():
    out = _handle("wool blanket, some pilling").json()           # home, fair: $7–11
    assert out["action"] == "donated" and "isn't worth the hassle" in out["summary"]


@pytest.mark.parametrize("pref,action", [("donate", "donated"), ("sell", "listed")])
def test_donor_preference_wins(pref, action):
    req = client.post("/api/requests", json=CHICAGO)                # demand would say donate
    assert req.status_code == 201
    assert _handle(preference=pref).json()["action"] == action


def test_unknown_draft_and_bad_preference():
    assert client.post("/api/items/drf_9999/handle").status_code == 404
    assert _handle(preference="burn it").status_code == 422


# ---- Modal brain (faked) ---------------------------------------------------------
class FakeModel:
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    async def ainvoke(self, messages):
        self.seen.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _calls(*names_args):
    return AIMessage("", tool_calls=[{"name": n, "args": a, "id": f"c{i}", "type": "tool_call"}
                                     for i, (n, a) in enumerate(names_args)])


@pytest.fixture
def model(monkeypatch, modal_mode):
    monkeypatch.setattr(config, "MODAL_AGENT_MODEL", "llm")
    holder = {}

    def install(replies):
        holder["m"] = FakeModel(replies)
        monkeypatch.setattr(concierge, "_model", lambda tools: holder["m"])
        return holder["m"]
    return install


def test_real_model_client_binds_the_four_tools(monkeypatch):
    """No network: just checks the ChatOpenAI client for Modal is built with our tools."""
    monkeypatch.setattr(config, "MODAL_ENDPOINT_URL", "https://example.modal.direct/v1")
    monkeypatch.setattr(config, "MODAL_AGENT_MODEL", "llm")
    draft_id = client.post("/api/items/parse", data={"zip": "1", "text": JACKET}).json()["draft_id"]
    bound = concierge._model(concierge._tools(concierge._Run(draft_id, "auto")))
    names = [t["function"]["name"] for t in bound.kwargs["tools"]]
    assert bound.kwargs["tool_choice"] == "required"
    assert names == ["get_price_quote", "check_local_demand", "list_for_sale", "donate_item"]
    price = bound.kwargs["tools"][2]["function"]["parameters"]["properties"]["price"]
    assert price["type"] == "number"
    assert bound.bound.model_name == "llm"
    assert str(bound.bound.openai_api_base) == "https://example.modal.direct/v1"


def test_model_drives_the_tools(model):
    fake = model([_calls(("get_price_quote", {}), ("check_local_demand", {})),
                  _calls(("list_for_sale", {"price": 21})),
                  AIMessage("Listed your jacket for $21 on Shopstr.")])
    out = _handle().json()
    assert out["brain"] == "modal" and out["action"] == "listed"
    assert out["listing"]["price"] == 21 and "listed it on Shopstr for $21" in out["summary"]
    assert out["steps"] == ["get_price_quote", "check_local_demand", "list_for_sale"]
    tool_results = [m for m in fake.seen[1] if m.type == "tool"]
    assert {m.name for m in tool_results} == {"get_price_quote", "check_local_demand"}
    assert '"low": 15' in next(m.content for m in tool_results if m.name == "get_price_quote")


def test_model_failure_hands_over_to_rules(model):
    model([_calls(("get_price_quote", {}), ("check_local_demand", {})),
           TimeoutError("cold start")])
    out = _handle().json()
    assert out["brain"] == "rules" and out["action"] == "listed"
    assert "Model unavailable (TimeoutError); switching to rules" in _concierge_messages()


def test_model_that_never_acts_is_finished_by_rules(model):
    model([AIMessage("Sounds like a nice jacket!")])
    out = _handle().json()
    assert out["brain"] == "rules" and out["action"] == "listed"
    assert out["steps"] == ["get_price_quote", "check_local_demand", "list_for_sale"]
    assert "The model didn't decide; finishing with rules" in _concierge_messages()


def test_model_cannot_both_sell_and_donate(model):
    model([_calls(("get_price_quote", {}), ("check_local_demand", {})),
           _calls(("list_for_sale", {"price": 20}), ("donate_item", {})),
           AIMessage("Done.")])
    out = _handle().json()
    assert out["action"] == "listed" and out["steps"].count("donate_item") == 0
    assert client.get("/api/items?status=available").json()["items"] == []


def test_bad_price_from_the_model_is_reported_back(model):
    fake = model([_calls(("get_price_quote", {}), ("check_local_demand", {})),
                  _calls(("list_for_sale", {"price": -5})),
                  _calls(("donate_item", {})),
                  AIMessage("Donated it instead.")])
    out = _handle().json()
    assert out["action"] == "donated"
    assert fake.seen[2][-1].type == "tool"        # what the model saw after the bad call
    assert fake.seen[2][-1].content == "Error: Price must be more than $0."
