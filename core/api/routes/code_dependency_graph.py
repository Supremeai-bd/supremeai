from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.security.authentication.rbac import get_current_user_token

router = APIRouter(
    prefix="/api/codeflow", tags=["codeflow"], dependencies=[Depends(get_current_user_token)]
)


class CodeFlowRequest(BaseModel):
    path: str
    depth: int | None = 1


class CodeFlowEdge(BaseModel):
    source: str
    target: str
    type: str


class CodeFlowNode(BaseModel):
    id: str
    label: str
    kind: str


class CodeFlowResponse(BaseModel):
    path: str
    nodes: list[CodeFlowNode]
    edges: list[CodeFlowEdge]


@router.post("/analyze", response_model=CodeFlowResponse)
async def analyze(req: CodeFlowRequest) -> CodeFlowResponse:
    """বাংলা মন্তব্য (2026-11-24 audit): আগে এই endpoint হার্ডকোডেড ডামি রেসপন্স
    (single node + 'stdlib' edge) দিত — বাস্তব কোনো গ্রাফ বিশ্লেষণ ছাড়াই।
    এখন Graphify AST ইঞ্জিন (scripts/ci/sync_graph_to_memory.py) থেকে সত্যিকারের
    1-hop dependents/dependencies রেসপন্স হিসেবে দেয়; ইঞ্জিন ব্যর্থ হলে সৎভাবে
    খালি গ্রাফ দেয়, ভান নয়।"""
    try:
        from scripts.ci.sync_graph_to_memory import analyze_blast_radius, load_or_build_graph

        graph = load_or_build_graph()
        blast = analyze_blast_radius(graph, [req.path])
        depth = max(1, min(int(req.depth or 1), 3))
        nodes = [CodeFlowNode(id=req.path, label=req.path, kind="file")]
        edges: list[CodeFlowEdge] = []
        dependents = (blast.get("direct_dependents") or [])[:20 * depth]
        for dep in dependents:
            nodes.append(CodeFlowNode(id=dep, label=dep, kind="file"))
            edges.append(CodeFlowEdge(source=req.path, target=dep, type="imported_by"))
        for upstream in (blast.get("upstream_dependencies") or [])[:20 * depth]:
            nodes.append(CodeFlowNode(id=upstream, label=upstream, kind="file"))
            edges.append(CodeFlowEdge(source=upstream, target=req.path, type="imports"))
        return CodeFlowResponse(path=req.path, nodes=nodes, edges=edges)
    except Exception as exc:  # noqa: BLE001 — ইঞ্জিন ব্যর্থতায় ভান নয়, সৎ খালি গ্রাফ
        from core.monitoring.logging_config import logger

        logger.warning(f"[codeflow] graph analysis unavailable for {req.path}: {exc}")
        return CodeFlowResponse(
            path=req.path,
            nodes=[CodeFlowNode(id=req.path, label=req.path, kind="file")],
            edges=[],
        )
