"""Tests for the /ai/build-graph LLM graph builder endpoint.

The OpenRouter call is mocked — we don't want tests burning real credit."""
# STL
import json
from unittest.mock import patch, MagicMock

# External
import pytest
from fastapi.testclient import TestClient

# Custom
from api.ai.schemas import BuiltGraph


# --- Pydantic validation of the graph shape -------------------------------

class TestBuiltGraphValidator:
  def test_valid_minimal_graph(self):
    g = BuiltGraph.model_validate({
      "nodes": [
        {"id": "trig", "type": "OnBar", "x": 0, "y": 0,
         "label": "On Bar", "params": {"timeframe": "1D"}},
        {"id": "buy", "type": "Buy", "x": 400, "y": 0,
         "label": "Buy", "params": {"size_type": "units", "amount": 10}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "buy",
         "sourceHandle": "out", "targetHandle": "in"},
      ],
    })
    assert len(g.nodes) == 2
    assert len(g.edges) == 1

  def test_empty_nodes_rejected(self):
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="at least one node"):
      BuiltGraph.model_validate({"nodes": [], "edges": []})

  def test_duplicate_node_ids_rejected(self):
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="node ids must be unique"):
      BuiltGraph.model_validate({
        "nodes": [
          {"id": "a", "type": "OnBar", "x": 0, "y": 0,
           "label": "", "params": {}},
          {"id": "a", "type": "Buy", "x": 0, "y": 0,
           "label": "", "params": {}},
        ],
        "edges": [],
      })

  def test_edge_referencing_missing_node_rejected(self):
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="is not a node id"):
      BuiltGraph.model_validate({
        "nodes": [
          {"id": "trig", "type": "OnBar", "x": 0, "y": 0,
           "label": "", "params": {}},
        ],
        "edges": [
          {"id": "e1", "source": "trig", "target": "ghost",
           "sourceHandle": "out", "targetHandle": "in"},
        ],
      })

  def test_invalid_source_handle_rejected(self):
    """MACD has macd/signal/histogram — `out` must not be accepted."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="has no output handle"):
      BuiltGraph.model_validate({
        "nodes": [
          {"id": "trig", "type": "OnBar", "x": 0, "y": 0, "label": "", "params": {}},
          {"id": "m", "type": "MACD", "x": 300, "y": 0, "label": "", "params": {}},
          {"id": "k0", "type": "Constant", "x": 300, "y": 100, "label": "", "params": {"value": 0}},
          {"id": "c", "type": "IfAbove", "x": 600, "y": 0, "label": "", "params": {}},
        ],
        "edges": [
          {"id": "e1", "source": "trig", "target": "m", "sourceHandle": "out", "targetHandle": "in"},
          {"id": "e2", "source": "trig", "target": "c", "sourceHandle": "out", "targetHandle": "in"},
          {"id": "e3", "source": "m", "target": "c", "sourceHandle": "out", "targetHandle": "a"},
          {"id": "e4", "source": "k0", "target": "c", "sourceHandle": "out", "targetHandle": "b"},
        ],
      })

  def test_invalid_target_handle_rejected(self):
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="has no input handle"):
      BuiltGraph.model_validate({
        "nodes": [
          {"id": "trig", "type": "OnBar", "x": 0, "y": 0, "label": "", "params": {}},
          {"id": "buy", "type": "Buy", "x": 300, "y": 0, "label": "", "params": {}},
        ],
        "edges": [
          {"id": "e1", "source": "trig", "target": "buy", "sourceHandle": "out", "targetHandle": "bogus"},
        ],
      })

  def test_unknown_node_type_rejected(self):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
      BuiltGraph.model_validate({
        "nodes": [
          {"id": "x", "type": "NotARealNode", "x": 0, "y": 0,
           "label": "", "params": {}},
        ],
        "edges": [],
      })


# --- Endpoint behaviour ---------------------------------------------------

_VALID_LLM_OUTPUT = {
  "graph": {
    "nodes": [
      {"id": "trig", "type": "OnBar", "x": 60, "y": 140,
       "label": "On Bar", "params": {"timeframe": "1D"}},
      {"id": "sma50", "type": "SMA", "x": 340, "y": 60,
       "label": "SMA 50", "params": {"period": 50}},
      {"id": "sma200", "type": "SMA", "x": 340, "y": 220,
       "label": "SMA 200", "params": {"period": 200}},
      {"id": "xup", "type": "IfCrossAbove", "x": 640, "y": 60,
       "label": "Cross", "params": {}},
      {"id": "buy", "type": "Buy", "x": 940, "y": 60,
       "label": "Buy", "params": {"size_type": "units", "amount": 100}},
    ],
    "edges": [
      {"id": "e1", "source": "trig", "target": "sma50",
       "sourceHandle": "out", "targetHandle": "in"},
      {"id": "e2", "source": "trig", "target": "sma200",
       "sourceHandle": "out", "targetHandle": "in"},
      {"id": "e3", "source": "trig", "target": "xup",
       "sourceHandle": "out", "targetHandle": "in"},
      {"id": "e4", "source": "sma50", "target": "xup",
       "sourceHandle": "out", "targetHandle": "a"},
      {"id": "e5", "source": "sma200", "target": "xup",
       "sourceHandle": "out", "targetHandle": "b"},
      {"id": "e6", "source": "xup", "target": "buy",
       "sourceHandle": "true", "targetHandle": "in"},
    ],
  },
  "notes": "Golden cross on SMA 50 / 200.",
}


def _mock_completion(content: str):
  mock_choice = MagicMock()
  mock_choice.message.content = content
  mock_resp = MagicMock()
  mock_resp.choices = [mock_choice]
  return mock_resp


def test_build_graph_requires_auth(client: TestClient):
  resp = client.post("/ai/build-graph", json={"prompt": "golden cross"})
  assert resp.status_code == 401


def test_build_graph_requires_api_key(auth_client: TestClient):
  """If OPENROUTER_API_KEY is empty, the endpoint returns 503."""
  with patch("api.ai.service.settings") as s:
    s.openrouter_api_key = ""
    resp = auth_client.post("/ai/build-graph", json={"prompt": "golden cross"})
  assert resp.status_code == 503


def test_build_graph_happy_path(auth_client: TestClient):
  mock_client = MagicMock()
  mock_client.chat.completions.create.return_value = _mock_completion(
    json.dumps(_VALID_LLM_OUTPUT)
  )
  with patch("api.ai.service.settings") as s, \
       patch("api.ai.service.OpenAI", return_value=mock_client):
    s.openrouter_api_key = "sk-test"
    s.openrouter_base_url = "https://openrouter.ai/api/v1"
    s.openrouter_model = "anthropic/claude-haiku-4.5"
    resp = auth_client.post(
      "/ai/build-graph",
      json={"prompt": "golden cross on AAPL"},
    )
  assert resp.status_code == 200, resp.json()
  body = resp.json()
  assert body["notes"].startswith("Golden cross")
  assert len(body["graph"]["nodes"]) == 5
  assert any(n["type"] == "IfCrossAbove" for n in body["graph"]["nodes"])


def test_build_graph_strips_markdown_fences(auth_client: TestClient):
  fenced = "```json\n" + json.dumps(_VALID_LLM_OUTPUT) + "\n```"
  mock_client = MagicMock()
  mock_client.chat.completions.create.return_value = _mock_completion(fenced)
  with patch("api.ai.service.settings") as s, \
       patch("api.ai.service.OpenAI", return_value=mock_client):
    s.openrouter_api_key = "sk-test"
    s.openrouter_base_url = "https://openrouter.ai/api/v1"
    s.openrouter_model = "anthropic/claude-haiku-4.5"
    resp = auth_client.post(
      "/ai/build-graph", json={"prompt": "golden cross"}
    )
  assert resp.status_code == 200


def test_build_graph_rejects_invalid_json(auth_client: TestClient):
  mock_client = MagicMock()
  mock_client.chat.completions.create.return_value = _mock_completion(
    "I can't help with that."
  )
  with patch("api.ai.service.settings") as s, \
       patch("api.ai.service.OpenAI", return_value=mock_client):
    s.openrouter_api_key = "sk-test"
    s.openrouter_base_url = "https://openrouter.ai/api/v1"
    s.openrouter_model = "anthropic/claude-haiku-4.5"
    resp = auth_client.post(
      "/ai/build-graph", json={"prompt": "test prompt"}
    )
  assert resp.status_code == 422
  assert "valid JSON" in resp.json()["detail"]


def test_build_graph_rejects_malformed_graph(auth_client: TestClient):
  bad = {"graph": {"nodes": [], "edges": []}, "notes": ""}
  mock_client = MagicMock()
  mock_client.chat.completions.create.return_value = _mock_completion(
    json.dumps(bad)
  )
  with patch("api.ai.service.settings") as s, \
       patch("api.ai.service.OpenAI", return_value=mock_client):
    s.openrouter_api_key = "sk-test"
    s.openrouter_base_url = "https://openrouter.ai/api/v1"
    s.openrouter_model = "anthropic/claude-haiku-4.5"
    resp = auth_client.post(
      "/ai/build-graph", json={"prompt": "test prompt"}
    )
  assert resp.status_code == 422


def test_build_graph_self_corrects_on_invalid_first_attempt(auth_client: TestClient):
  """First LLM response has a bogus handle; retry fixes it."""
  bad_output = {
    "graph": {
      "nodes": [
        {"id": "trig", "type": "OnBar", "x": 0, "y": 0, "label": "", "params": {}},
        {"id": "m", "type": "MACD", "x": 300, "y": 0, "label": "", "params": {}},
        {"id": "k0", "type": "Constant", "x": 300, "y": 100, "label": "", "params": {"value": 0}},
        {"id": "c", "type": "IfAbove", "x": 600, "y": 0, "label": "", "params": {}},
        {"id": "buy", "type": "Buy", "x": 900, "y": 0, "label": "", "params": {}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "m", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e2", "source": "trig", "target": "c", "sourceHandle": "out", "targetHandle": "in"},
        # BOGUS: MACD has no "out" handle — validator rejects.
        {"id": "e3", "source": "m", "target": "c", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e4", "source": "k0", "target": "c", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e5", "source": "c", "target": "buy", "sourceHandle": "true", "targetHandle": "in"},
      ],
    },
    "notes": "bad attempt",
  }
  good_output = dict(bad_output)
  good_output["graph"] = dict(bad_output["graph"])
  good_output["graph"]["edges"] = list(bad_output["graph"]["edges"])
  # Fix the MACD handle on retry.
  good_output["graph"]["edges"][2] = {
    "id": "e3", "source": "m", "target": "c",
    "sourceHandle": "histogram", "targetHandle": "a",
  }
  good_output["notes"] = "corrected"

  mock_client = MagicMock()
  mock_client.chat.completions.create.side_effect = [
    _mock_completion(json.dumps(bad_output)),
    _mock_completion(json.dumps(good_output)),
  ]
  with patch("api.ai.service.settings") as s, \
       patch("api.ai.service.OpenAI", return_value=mock_client):
    s.openrouter_api_key = "sk-test"
    s.openrouter_base_url = "https://openrouter.ai/api/v1"
    s.openrouter_model = "anthropic/claude-haiku-4.5"
    resp = auth_client.post(
      "/ai/build-graph", json={"prompt": "MACD histogram positive"}
    )
  assert resp.status_code == 200, resp.json()
  assert resp.json()["notes"] == "corrected"
  assert mock_client.chat.completions.create.call_count == 2
  # The retry call must include the assistant's bad reply + a correction user message.
  second_call = mock_client.chat.completions.create.call_args_list[1]
  sent_messages = second_call.kwargs["messages"]
  assert len(sent_messages) == 4  # system + user + assistant(bad) + user(error)
  assert "failed validation" in sent_messages[-1]["content"]


def test_build_graph_gives_up_after_one_retry(auth_client: TestClient):
  """If both attempts are invalid, 422 is returned — no infinite loop."""
  bad = {"graph": {"nodes": [], "edges": []}, "notes": ""}
  mock_client = MagicMock()
  mock_client.chat.completions.create.side_effect = [
    _mock_completion(json.dumps(bad)),
    _mock_completion(json.dumps(bad)),
  ]
  with patch("api.ai.service.settings") as s, \
       patch("api.ai.service.OpenAI", return_value=mock_client):
    s.openrouter_api_key = "sk-test"
    s.openrouter_base_url = "https://openrouter.ai/api/v1"
    s.openrouter_model = "anthropic/claude-haiku-4.5"
    resp = auth_client.post(
      "/ai/build-graph", json={"prompt": "something weird"}
    )
  assert resp.status_code == 422
  assert mock_client.chat.completions.create.call_count == 2


def test_build_graph_rejects_short_prompt(auth_client: TestClient):
  resp = auth_client.post("/ai/build-graph", json={"prompt": "a"})
  assert resp.status_code == 422
