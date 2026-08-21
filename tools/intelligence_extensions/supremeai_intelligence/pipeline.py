from dataclasses import dataclass
@dataclass
class PromotionGate: eligible:bool; reasons:list[str]
class IntelligenceGate:
    def __init__(self,evidence,contradictions,execution,curator):self.evidence=evidence;self.contradictions=contradictions;self.execution=execution;self.curator=curator
    async def evaluate(self,artifact,evidence_claims,python_code=None,test_code=None):
        reasons=[]
        ev=await self.evidence.verify(evidence_claims)
        if evidence_claims and not all(x.verified for x in ev):reasons.append('Evidence verification failed')
        c=await self.contradictions.inspect(str(artifact.get('artifact_id','')),str(artifact.get('claim',''))+'\n'+str(artifact.get('solution','')))
        if not c.safe_to_promote:reasons.append('Contradiction found in existing memory')
        if python_code and not (await self.execution.verify_python(python_code,test_code=test_code)).passed:reasons.append('Execution verification failed')
        d=self.curator.decide(artifact)
        if d.action not in {'promote','retain'}:reasons.append(f'Curator={d.action}')
        return PromotionGate(not reasons,reasons)
