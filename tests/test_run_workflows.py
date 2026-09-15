"""HTTP lifecycle, export completeness and event-loop responsiveness."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

from lib.evidence import ANALYSIS_VERSION, evidence_hash


def test_query_returns_identity_and_exposes_cancel_resume(client, monkeypatch):
    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()
    monkeypatch.setattr(client.app.state.services.query_processor.ai_service, 'get_model_response', blocked)
    pdx = client.get('/api/paradoxes').json()[0]['id']
    response = client.post('/api/query', json={'modelName': 'test/model', 'paradoxId': pdx, 'iterations': 1})
    assert response.status_code == 202
    rid = response.json()['runId']
    fragment = client.get(f'/fragments/runs/{rid}')
    assert 'Cancel run' in fragment.text and 'every 2s' in fragment.text
    assert '0 / 1 iterations' in fragment.text
    assert client.post(f'/api/runs/{rid}/cancel').json()['status'] == 'cancelled'
    assert 'Resume run' in client.get(f'/fragments/runs/{rid}').text
    assert client.post(f'/api/runs/{rid}/resume').status_code == 200
    assert client.post(f'/api/runs/{rid}/resume').status_code == 400
    client.post(f'/api/runs/{rid}/cancel')


def test_json_export_retains_audit_fields_and_selected_insight(client):
    run = {'modelName': 'test/model', 'paradoxId': 'p', 'prompt': 'stimulus', 'params': {'temperature': 0.3},
           'options': [], 'responses': [{'iteration': 1, 'raw': 'raw output', 'optionOrder': {'1': 2, '2': 1}}]}
    run['insights'] = [{'analysisVersion': ANALYSIS_VERSION, 'evidenceHash': evidence_hash(run), 'analystModel': 'analyst', 'content': {'dominant_framework': 'Duty'}}]
    rid = client.portal.call(client.app.state.services.storage.create_run, 'model', run)
    exported = client.get(f'/api/runs/{rid}/export').json()
    assert exported['export_kind'] == 'reproducibility'
    assert exported['insight']['analyst_model'] == 'analyst'
    assert exported['complete_run']['responses'][0]['optionOrder'] == {'1': 2, '2': 1}
    assert exported['complete_run']['prompt'] == 'stimulus'
    assert exported['complete_run']['params'] == {'temperature': 0.3}


def test_health_and_cancel_remain_responsive_during_html_render(client, monkeypatch):
    services = client.app.state.services
    entered = threading.Event(); release = threading.Event()
    def render(*args, **kwargs):
        entered.set()
        assert release.wait(3), 'test must release renderer'
        return '<html>Report</html>'
    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()
    monkeypatch.setattr(services.report_generator, 'generate_html_report', render)
    monkeypatch.setattr(services.query_processor.ai_service, 'get_model_response', blocked)
    pdx = client.get('/api/paradoxes').json()[0]['id']
    run = client.post('/api/query', json={'modelName': 'test/model', 'paradoxId': pdx, 'iterations': 1}).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        download = pool.submit(client.get, f"/reports/runs/{run['runId']}")
        try:
            assert entered.wait(1)
            assert pool.submit(client.get, '/health').result(timeout=1).status_code == 200
            cancellation = pool.submit(client.post, f"/api/runs/{run['runId']}/cancel").result(timeout=1)
            assert cancellation.json()['status'] == 'cancelled'
        finally:
            release.set()
        assert download.result(timeout=2).status_code == 200


def test_lab_launch_claims_once_and_returns_promptly(client, monkeypatch):
    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()
    monkeypatch.setattr(client.app.state.services.query_processor.ai_service, 'get_model_response', blocked)
    pdx = client.get('/api/paradoxes').json()[0]['id']
    exp = client.post('/api/experiments', json={'title': 'matrix', 'paradoxIds': [pdx], 'conditions': [{'modelName': 'test/model', 'iterations': 1}]}).json()
    route = f"/api/experiments/{exp['id']}/execute"
    assert client.post(route).status_code == 202
    assert client.post(route).status_code == 409
    assert 'experimentIterations' in client.get('/experiments').text


def test_actual_html_reports_are_printable_and_make_no_model_calls(client, monkeypatch):
    from lib.reporting import ReportGenerator
    services = client.app.state.services
    services.report_generator = ReportGenerator('templates')
    provider = AsyncMock(side_effect=AssertionError('Report views must not call models'))
    monkeypatch.setattr(services.query_processor.ai_service, 'get_model_response', provider)
    pdx = {'id':'p','title':'Test scenario','promptTemplate':'Saved stimulus','options':[{'id':1,'label':'A','description':'A'},{'id':2,'label':'B','description':'B'}]}
    run = {'modelName':'test/model','paradoxId':'p','paradox':pdx,'options':pdx['options'], 'responses':[], 'summary':{}}
    rid = client.portal.call(services.storage.create_run, 'model', run)
    rid2 = client.portal.call(services.storage.create_run, 'model', dict(run))
    for url in [f'/reports/runs/{rid}', f'/reports/compare?run_ids={rid},{rid2}']:
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/html')
        assert 'Print / Save as PDF' in response.text
        assert 'Download HTML' in response.text
        assert '@media print' in response.text
        assert 'window.print()' in response.text
        assert '<script src=' not in response.text and '<link rel="stylesheet"' not in response.text
    assert provider.await_count == 0
    assert client.get(f'/reports/compare?run_ids={rid},{rid}').status_code == 400
    assert client.get(f'/api/runs/{rid}/pdf').status_code == 404


def test_insight_slides_use_saved_evidence_escape_text_and_split_long_insights(client, monkeypatch):
    from lib.reporting import ReportGenerator
    services = client.app.state.services
    services.report_generator = ReportGenerator('templates')
    provider = AsyncMock(side_effect=AssertionError('Slides must not call models'))
    monkeypatch.setattr(services.query_processor.ai_service, 'get_model_response', provider)
    pdx = {'id': 'p', 'title': '<script>unsafe</script>', 'promptTemplate': 'Saved question',
           'options': [{'id': 1, 'label': 'A', 'description': 'First option'}]}
    run = {'modelName': 'test/model', 'paradoxId': 'p', 'paradox': pdx, 'options': pdx['options'],
           'status': 'completed', 'responses': [], 'summary': {}}
    run['insights'] = [{'analysisVersion': ANALYSIS_VERSION, 'evidenceHash': evidence_hash(run),
                        'analystModel': 'analyst', 'content': {'key_insights': ['Saved insight. ' * 90]}}]
    rid = client.portal.call(services.storage.create_run, 'model', run)
    response = client.get(f'/reports/runs/{rid}?view=slides')
    assert response.status_code == 200
    assert 'Save LinkedIn slideshow PDF' in response.text
    assert 'Saved insight.' in response.text and 'continued' in response.text
    assert '<script>unsafe</script>' not in response.text
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in response.text
    assert 'size: 10in 10in' in response.text and 'break-after: page' in response.text
    assert 'window.print()' in response.text
    assert 'Saved analyst interpretation' in response.text
    assert '<script src=' not in response.text
    assert 'LinkedIn insight slides' in client.get(f'/reports/runs/{rid}').text
    fragment = client.get(f'/fragments/runs/{rid}')
    assert fragment.status_code == 200 and f'{rid}?view=slides' in fragment.text
    assert client.get(f'/reports/runs/{rid}?view=invalid').status_code == 400
    assert provider.await_count == 0


def test_report_formats_share_render_limit_and_keep_health_responsive(client, monkeypatch):
    from lib.reporting import ReportGenerator

    services = client.app.state.services
    services.report_generator = ReportGenerator('templates')
    release = threading.Event()
    two_started = threading.Event()
    third_started = threading.Event()
    lock = threading.Lock()
    active = 0
    peak = 0
    started = 0

    def render(*args, **kwargs):
        nonlocal active, peak, started
        with lock:
            active += 1
            started += 1
            peak = max(peak, active)
            if started == 2:
                two_started.set()
            if started == 3:
                third_started.set()
        try:
            assert release.wait(3), 'test must release renderers'
            return '<html>Rendered</html>'
        finally:
            with lock:
                active -= 1

    for method in ('generate_html_report', 'generate_insight_slides', 'generate_comparison_html'):
        monkeypatch.setattr(services.report_generator, method, render)
    pdx = {'id': 'p', 'title': 'Test', 'promptTemplate': 'Saved scenario',
           'options': [{'id': 1, 'label': 'A', 'description': 'A'}]}
    run = {'modelName': 'test/model', 'paradoxId': 'p', 'paradox': pdx,
           'options': pdx['options'], 'responses': [], 'summary': {}}
    rid = client.portal.call(services.storage.create_run, 'model', run)
    rid2 = client.portal.call(services.storage.create_run, 'model', dict(run))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(client.get, f'/reports/runs/{rid}'),
                   pool.submit(client.get, f'/reports/runs/{rid}?view=slides')]
        try:
            assert two_started.wait(1)
            futures.append(pool.submit(client.get, f'/reports/compare?run_ids={rid},{rid2}'))
            assert pool.submit(client.get, '/health').result(timeout=1).status_code == 200
            assert not third_started.wait(0.15), 'third report must wait for a render slot'
        finally:
            release.set()
        assert all(future.result(timeout=2).status_code == 200 for future in futures)
    assert started == 3 and peak == 2
