from supremeai_intelligence.model_router_economist import ModelRouterEconomist,ModelStats
from supremeai_intelligence.failure_pattern_miner import FailurePatternMiner
print(ModelRouterEconomist([ModelStats('a','fast'),ModelStats('b','reasoner')]).choose(complexity=.85,risk=.8))
print(FailurePatternMiner().mine([{'category':'timeout','message':'request timeout 10'},{'category':'timeout','message':'request timeout 20'}]))
