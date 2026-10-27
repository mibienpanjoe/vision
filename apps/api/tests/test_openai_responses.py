"""The OpenAI wire boundary, using a local HTTP server and synthetic credentials only."""

import copy
import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from app.providers.contracts import (
    ProviderInputTooLarge,
    ProviderRateLimited,
    ProviderUnavailable,
    adapter_version,
)
from app.providers.execution import execute
from app.providers.openai_responses import OpenAIResponses
from app.services.visualization.specification import consolidation_adapter
from tests.test_provider_contracts import Names, request


@pytest.fixture
def endpoint():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.server.seen.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            status, payload = self.server.reply
            if hasattr(self.server, 'factory'):
                payload = self.server.factory(self.server.seen[-1][1])
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    server.seen = []
    server.reply = (200, {
        'status': 'completed', 'model': 'gpt-6-luna',
        'usage': {'input_tokens': 40, 'output_tokens': 12},
        'output': [{'type': 'reasoning', 'summary': []}, {'type': 'message', 'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': '{"names":["Wren"]}'}]}],
    })
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, OpenAIResponses('synthetic-key', base_url=f'http://127.0.0.1:{server.server_port}/v1')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_responses_uses_tool_free_strict_json_and_preserves_usage(endpoint):
    server, adapter = endpoint
    result = execute(adapter, request('Wren'), Names)
    assert result.output == Names(names=['Wren'])
    assert (result.record.provider, result.record.model, result.record.usage.input_tokens,
            result.record.usage.output_tokens) == ('openai', 'gpt-6-luna', 40, 12)
    assert result.record.config['adapter']['reasoning'] == 'none'
    path, body = server.seen[0]
    assert path == '/v1/responses'
    assert body['store'] is False and body['reasoning'] == {'effort': 'none'}
    assert body['max_output_tokens'] == 2048
    assert 'temperature' not in body and 'tools' not in body and 'previous_response_id' not in body
    assert body['input'] == [{'role': 'user', 'content': '{"sources": [{"ref": "passage:0", "text": "Wren"}]}'}]
    assert body['text']['format']['strict'] is True
    assert body['text']['format']['schema']['additionalProperties'] is False


def test_wire_schema_requires_defaulted_fields_without_mutating_the_domain_schema(endpoint):
    from app.providers.consolidation import Consolidation
    from app.providers.contracts import compose

    server, adapter = endpoint
    call = compose(request('Wren'), Consolidation)
    original = copy.deepcopy(call.output_schema)
    adapter.complete(call)
    schema = server.seen[0][1]['text']['format']['schema']

    def check(node):
        if isinstance(node, dict):
            if node.get('type') == 'object':
                assert node['additionalProperties'] is False
                assert set(node['required']) == set(node['properties'])
            assert 'default' not in node
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(schema)
    assert call.output_schema == original


@pytest.mark.parametrize(('code', 'error'), [(401, ProviderUnavailable), (403, ProviderUnavailable),
    (413, ProviderInputTooLarge), (429, ProviderRateLimited), (500, ProviderUnavailable)])
def test_http_failures_are_safe_and_do_not_retry_paid_requests(endpoint, code, error):
    from app.providers.contracts import compose

    server, adapter = endpoint
    server.reply = (code, {'error': {'message': 'source text or credentials must never leave the adapter'}})
    with pytest.raises(error) as caught:
        adapter.complete(compose(request('Wren'), Names))
    assert str(caught.value) == '' and len(server.seen) == 1


@pytest.mark.parametrize(('status', 'content', 'outcome'), [
    ('incomplete', [{'type': 'output_text', 'text': '{"names":["Wren"]}'}], 'budget_exhausted'),
    ('completed', [{'type': 'refusal', 'refusal': 'private refusal text'}], 'provider_unavailable'),
])
def test_incomplete_or_refused_output_never_reaches_canon_but_keeps_charged_usage(endpoint, status, content, outcome):
    server, adapter = endpoint
    server.reply[1]['status'] = status
    server.reply[1]['incomplete_details'] = {'reason': 'max_output_tokens'} if status == 'incomplete' else None
    server.reply[1]['output'][1]['content'] = content
    result = execute(adapter, request('Wren'), Names)
    assert result.output is None and result.record.outcome == outcome
    assert result.record.usage.output_tokens == 12
    assert len(server.seen) == 1


@pytest.mark.parametrize('broken', [None, {}, {'input_tokens': -1, 'output_tokens': 1},
                                  {'input_tokens': 'unknown', 'output_tokens': 1}])
def test_missing_or_malformed_usage_is_not_recorded_as_a_free_success(endpoint, broken):
    server, adapter = endpoint
    server.reply[1]['usage'] = broken
    result = execute(adapter, request('Wren'), Names)
    assert result.output is None and result.record.outcome == 'provider_unavailable'


@pytest.mark.parametrize('failure', [TimeoutError(), urllib.error.URLError(TimeoutError())])
def test_transport_timeouts_return_the_common_safe_outcome(monkeypatch, failure):
    def unavailable(*args, **kwargs):
        raise failure

    monkeypatch.setattr('urllib.request.urlopen', unavailable)
    result = execute(OpenAIResponses('synthetic-key'), request('Wren'), Names)
    assert result.record.outcome == 'timeout' and result.output is None


def test_openai_selection_is_explicit_and_never_falls_back_to_another_provider(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'synthetic-groq')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-openai')
    monkeypatch.delenv('VISION_QUERY_PROVIDER', raising=False)
    assert consolidation_adapter().provider == 'groq'
    monkeypatch.setenv('VISION_QUERY_PROVIDER', 'openai')
    assert consolidation_adapter().provider == 'openai'
    monkeypatch.delenv('OPENAI_API_KEY')
    assert consolidation_adapter() is None
    monkeypatch.setenv('VISION_QUERY_PROVIDER', 'typo')
    assert consolidation_adapter() is None


def test_openai_defaults_leave_the_bounded_output_budget_for_the_answer(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    monkeypatch.delenv('VISION_OPENAI_MODEL', raising=False)
    monkeypatch.delenv('VISION_OPENAI_REASONING', raising=False)
    adapter = OpenAIResponses.from_environment()
    assert adapter.model == 'gpt-6-luna' and adapter.effort == 'none'


def test_reasoning_configuration_changes_the_cache_and_derivation_identity():
    low, high = OpenAIResponses('synthetic-key', effort='low'), OpenAIResponses('synthetic-key', effort='high')
    assert low.model == high.model == 'gpt-6-luna'
    assert adapter_version(low) != adapter_version(high)


def test_wire_schema_preserves_a_field_literally_named_default():
    from app.providers.openai_responses import strict_schema

    wire = strict_schema({'type': 'object', 'properties': {'default': {'type': 'string', 'default': 'x'}}})
    assert wire['required'] == ['default'] and wire['properties']['default'] == {'type': 'string'}


def test_cancellation_still_wins_after_an_incomplete_charged_response(endpoint):
    server, adapter = endpoint
    server.reply[1]['status'] = 'incomplete'
    server.reply[1]['incomplete_details'] = {'reason': 'max_output_tokens'}
    checks = iter([False, True])
    result = execute(adapter, request('Wren'), Names, cancelled=lambda: next(checks))
    assert result.record.outcome == 'cancelled' and result.record.usage.output_tokens == 12


@pytest.mark.integration
def test_openai_wire_output_is_grounded_stored_and_cached_separately_by_effort(api, endpoint, monkeypatch):
    from app.models.model_runs import ModelRun
    from app.services.visualization import specification
    from sqlalchemy import select
    from tests.test_appearance_states import annotated_consolidation
    from tests.test_visualization_api import store

    server, adapter = endpoint
    _, _, _, story = api

    def reply(body):
        output = annotated_consolidation(json.loads(body['input'][0]['content'])['sources'])
        return {**server.reply[1], 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(output)}]}]}

    server.factory = reply
    monkeypatch.setattr(specification, 'consolidation_adapter', lambda: adapter)
    first = store(api, 'openai-default', query='Arthur at home after the war')
    assert first.status_code == 201 and first.json()['result']['outcome'] == 'resolved'
    stored = first.json()['visualization']
    cached = store(api, 'openai-cached', query='Arthur at home after the war')
    assert cached.json()['result'] == stored['result'] and len(server.seen) == 1
    monkeypatch.setattr(specification, 'consolidation_adapter', lambda: OpenAIResponses(
        'synthetic-key', effort='high', base_url=adapter.base_url))
    changed = store(api, 'openai-high', query='Arthur at home after the war')
    assert changed.json()['result']['outcome'] == 'resolved' and len(server.seen) == 2
    assert changed.json()['result']['data']['lineage']['consolidation_id'] != \
        stored['result']['data']['lineage']['consolidation_id']
    rows = story.db.scalars(select(ModelRun).where(ModelRun.provider == 'openai')).all()
    assert {r.config['adapter']['reasoning'] for r in rows} == {'none', 'high'}
    assert all(r.outcome == 'succeeded' and r.input_tokens == 40 for r in rows)
