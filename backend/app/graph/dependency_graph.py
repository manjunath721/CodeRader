"""
Module dependency graph analysis — risk-model.md §4, master spec §16/§20.
"""
import networkx as nx


def build_dependency_graph(edges: list[tuple[str, str]]) -> nx.DiGraph:
    """edges: list of (module_id, depends_on_module_id) meaning module_id -> depends on -> the other.
    We store the graph so that an edge A->B means "B depends on A" (i.e. impact flows A to B),
    matching risk-model.md §4's convention.
    """
    g = nx.DiGraph()
    for module_id, depends_on_id in edges:
        g.add_edge(depends_on_id, module_id)  # depends_on -> dependent (impact flows this way)
    return g


def centrality_scores(g: nx.DiGraph) -> dict[str, float]:
    """in-degree + out-degree, used as the raw `dependency_centrality` risk factor."""
    return {n: g.in_degree(n) + g.out_degree(n) for n in g.nodes}


def dependency_concentration_hhi(g: nx.DiGraph) -> float:
    """HHI of in-degree distribution across modules, normalized to 0-1, for the
    project resilience `dependency_concentration` component."""
    in_degrees = [d for _, d in g.in_degree()]
    total = sum(in_degrees)
    if total == 0:
        return 0.0
    shares = [d / total for d in in_degrees]
    hhi = sum(s ** 2 for s in shares)  # 0-1 already since shares sum to 1
    return round(hhi, 4)


def propagate_risk(g: nx.DiGraph, source_module_id: str, decay: float = 0.6) -> dict[str, float]:
    """
    risk-model.md §4: direct_impact(source)=1.0; propagated_impact(m') =
    decay^(shortest_path_length) for each m' reachable from source.
    """
    if source_module_id not in g:
        return {source_module_id: 1.0}
    lengths = nx.single_source_shortest_path_length(g, source_module_id)
    return {node: round(decay ** dist, 4) for node, dist in lengths.items()}
