import asyncio
from supremeai_intelligence.contracts import SourceRecord
from supremeai_intelligence.evidence_verifier import EvidenceVerifier
from supremeai_intelligence.failure_pattern_miner import FailurePatternMiner
from supremeai_intelligence.execution_verifier import ExecutionVerifier
from supremeai_intelligence.memory_curator import MemoryCurator
from supremeai_intelligence.model_router_economist import ModelRouterEconomist,ModelStats

def test_evidence():
    async def r(c):return [SourceRecord('s','test',content=c,reliability=.95)]
    assert asyncio.run(EvidenceVerifier(r).verify(['x']))[0].verified

def test_failure():
    p=FailurePatternMiner().mine([{'category':'timeout','message':'timeout 10'},{'category':'timeout','message':'timeout 20'}]);assert len(p)==1 and p[0].recurrence==2

def test_exec():assert asyncio.run(ExecutionVerifier().verify_python('def f(): return 1')).passed

def test_curator():assert MemoryCurator().decide({'memory_id':'m','confidence':.9,'verification_status':'verified'}).action=='promote'

def test_router():
    d=ModelRouterEconomist([ModelStats('a','x'),ModelStats('b','y'),ModelStats('c','z')]).choose(complexity=.9,risk=.9);assert len(d.models)==3
