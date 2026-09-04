"""Contract tests for semantically specific network-graph model identifiers."""

from api.network import NetworkGraphEdge, NetworkGraphNode, NetworkGraphResponse


def test_network_graph_models_use_specific_owned_names_and_legacy_wire_aliases() -> None:
    """Keep owned names specific while preserving the established JSON response shape."""
    network_node = NetworkGraphNode(
        node_id="member@example.com",
        node_label="member@example.com",
    )
    network_edge = NetworkGraphEdge(
        source_node_id="member@example.com",
        target_node_id="partner@example.com",
        message_count=3,
    )
    graph_response = NetworkGraphResponse(
        network_nodes=[network_node],
        network_edges=[network_edge],
    )

    assert set(NetworkGraphNode.model_fields) == {"node_id", "node_label"}
    assert set(NetworkGraphEdge.model_fields) == {
        "source_node_id",
        "target_node_id",
        "message_count",
    }
    assert set(NetworkGraphResponse.model_fields) == {"network_nodes", "network_edges"}
    assert graph_response.model_dump() == {
        "network_nodes": [
            {
                "node_id": "member@example.com",
                "node_label": "member@example.com",
            }
        ],
        "network_edges": [
            {
                "source_node_id": "member@example.com",
                "target_node_id": "partner@example.com",
                "message_count": 3,
            }
        ],
    }
    assert graph_response.model_dump(by_alias=True) == {
        "nodes": [{"id": "member@example.com", "label": "member@example.com"}],
        "edges": [
            {
                "source": "member@example.com",
                "target": "partner@example.com",
                "weight": 3,
            }
        ],
    }
