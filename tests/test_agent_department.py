from unittest.mock import MagicMock
from brain.agent_department import CodingAgent, ReviewAgent, QAAgent, AgentDepartment


def _make_model_router():
    return MagicMock()


def test_coding_agent_success():
    router = _make_model_router()
    router.route_and_generate.return_value = {'success': True, 'text': 'code'}
    agent = CodingAgent(router)
    result = agent.execute('build feature')
    assert result['success'] is True
    assert result['role'] == 'coding-expert'


def test_coding_agent_failure():
    router = _make_model_router()
    router.route_and_generate.return_value = {'success': False, 'error': 'upstream'}
    agent = CodingAgent(router)
    result = agent.execute('build feature')
    assert result['success'] is False


def test_review_agent_output():
    router = _make_model_router()
    router.route_and_generate.return_value = {'success': True, 'text': 'review'}
    agent = ReviewAgent(router)
    result = agent.execute('review PR')
    assert result['success'] is True


def test_qa_agent_output():
    router = _make_model_router()
    router.route_and_generate.return_value = {'success': True, 'text': 'tests'}
    agent = QAAgent(router)
    result = agent.execute('create tests')
    assert result['success'] is True


def test_agent_department_unknown():
    dept = AgentDepartment(_make_model_router())
    result = dept.run('unknown', 'task')
    assert result['success'] is False


def test_agent_department_known():
    dept = AgentDepartment(_make_model_router())
    dept.model_router.route_and_generate.return_value = {'success': True, 'text': 'ok'}
    result = dept.run('coding', 'task')
    assert result['success'] is True
