"""
Knowledge graph construction — master spec §16. Builds a NetworkX graph and
serializes it to a plain node/edge list the frontend (React Flow / D3) can
render directly, with optional developer/module filtering.
"""
import networkx as nx


def build_knowledge_graph(
    developers: list[dict],  # [{id, name}]
    modules: list[dict],  # [{id, name}]
    knowledge_edges: list[dict],  # [{developer_id, module_id, score}]
    dependency_edges: list[tuple[str, str]],  # (module_id, depends_on_module_id)
) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for d in developers:
        g.add_node(f"dev:{d['id']}", type="Developer", label=d["name"])
    for m in modules:
        g.add_node(f"mod:{m['id']}", type="Module", label=m["name"])
    for e in knowledge_edges:
        g.add_edge(
            f"dev:{e['developer_id']}", f"mod:{e['module_id']}",
            relation="contributes_to", weight=e["score"],
        )
    for module_id, depends_on_id in dependency_edges:
        g.add_edge(f"mod:{module_id}", f"mod:{depends_on_id}", relation="depends_on", weight=1.0)
    return g


def serialize_for_frontend(
    g: nx.MultiDiGraph, developer_filter: str | None = None, module_filter: str | None = None
) -> dict:
    """Returns {"nodes": [...], "edges": [...]} ready for React Flow / D3.
    Filtering keeps a node if it matches directly, or is connected to a
    matching developer/module node (so selecting a developer highlights
    their whole knowledge network, per §28).
    """
    keep_nodes = set(g.nodes)
    if developer_filter:
        target = f"dev:{developer_filter}"
        keep_nodes = {target} | set(nx.node_connected_component(g.to_undirected(), target)) if target in g else set()
    elif module_filter:
        target = f"mod:{module_filter}"
        keep_nodes = {target} | set(nx.node_connected_component(g.to_undirected(), target)) if target in g else set()

    nodes = [
        {"id": n, "type": data["type"], "label": data["label"]}
        for n, data in g.nodes(data=True)
        if n in keep_nodes
    ]
    edges = [
        {"source": u, "target": v, "relation": data["relation"], "weight": data["weight"]}
        for u, v, data in g.edges(data=True)
        if u in keep_nodes and v in keep_nodes
    ]
    return {"nodes": nodes, "edges": edges}
