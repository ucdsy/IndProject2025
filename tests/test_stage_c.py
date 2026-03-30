from __future__ import annotations

import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.stage_c_selector import StageCConfig, select_agents_for_subtasks


ROOT = Path(__file__).resolve().parents[1]


class StageCSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = NamespaceResolver.from_jsonl(
            ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"
        )

    def test_stage_c_filters_exact_routing_fqdn(self) -> None:
        snapshot = {
            "snapshot_id": "snap1",
            "generated_at": "2026-03-26T10:00:00Z",
            "agents": [
                {
                    "agent_id": 1,
                    "name": "A",
                    "display_name_cn": "A",
                    "agent_code": "agent-a",
                    "agent_fqdn": "agent-a.agent.itinerary.travel.cn",
                    "routing_fqdn": "itinerary.travel.cn",
                    "endpoint": "http://a.local/invoke",
                    "provider": "a.local",
                    "status": "online",
                    "last_heartbeat_at": "2026-03-26T10:00:00Z",
                    "tags": ["travel.itinerary", "travel.plan"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "exposure_count_agent": 0,
                    "mode": "simulated",
                    "protocol": "http_json",
                },
                {
                    "agent_id": 2,
                    "name": "B",
                    "display_name_cn": "B",
                    "agent_code": "agent-b",
                    "agent_fqdn": "agent-b.agent.weather.cn",
                    "routing_fqdn": "weather.cn",
                    "endpoint": "http://b.local/invoke",
                    "provider": "b.local",
                    "status": "online",
                    "last_heartbeat_at": "2026-03-26T10:00:00Z",
                    "tags": ["weather.query"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "exposure_count_agent": 0,
                    "mode": "simulated",
                    "protocol": "http_json",
                },
            ],
        }
        result = select_agents_for_subtasks(
            subtasks=[{"need": "itinerary", "routing_fqdn": "itinerary.travel.cn", "role": "primary"}],
            registry_snapshot=snapshot,
            resolver=self.resolver,
            top_k=5,
            config=StageCConfig(),
        )
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(len(result["groups"][0]["agents"]), 1)
        self.assertEqual(result["groups"][0]["agents"][0]["agent_id"], 1)
        self.assertEqual(result["selection_trace"]["groups"][0]["filtered_out_reasons"]["routing_fqdn_mismatch"], 1)

    def test_stage_c_prefers_stronger_tag_and_exposure_profile(self) -> None:
        snapshot = {
            "snapshot_id": "snap2",
            "generated_at": "2026-03-26T10:00:00Z",
            "agents": [
                {
                    "agent_id": 1,
                    "name": "General",
                    "display_name_cn": "General",
                    "agent_code": "agent-general",
                    "agent_fqdn": "agent-general.agent.itinerary.travel.cn",
                    "routing_fqdn": "itinerary.travel.cn",
                    "endpoint": "http://general.local/invoke",
                    "provider": "general.local",
                    "status": "online",
                    "last_heartbeat_at": "2026-03-26T10:00:00Z",
                    "tags": ["travel.plan"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "exposure_count_agent": 10,
                    "mode": "simulated",
                    "protocol": "http_json",
                },
                {
                    "agent_id": 2,
                    "name": "Specialist",
                    "display_name_cn": "Specialist",
                    "agent_code": "agent-specialist",
                    "agent_fqdn": "agent-specialist.agent.itinerary.travel.cn",
                    "routing_fqdn": "itinerary.travel.cn",
                    "endpoint": "http://specialist.local/invoke",
                    "provider": "specialist.local",
                    "status": "online",
                    "last_heartbeat_at": "2026-03-26T10:00:00Z",
                    "tags": ["travel.plan", "travel.itinerary", "travel.routing"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "exposure_count_agent": 0,
                    "mode": "simulated",
                    "protocol": "http_json",
                },
            ],
        }
        result = select_agents_for_subtasks(
            subtasks=[{"need": "itinerary", "routing_fqdn": "itinerary.travel.cn", "role": "primary"}],
            registry_snapshot=snapshot,
            resolver=self.resolver,
            top_k=2,
            config=StageCConfig(),
        )
        top_agents = result["groups"][0]["agents"]
        self.assertEqual(top_agents[0]["agent_id"], 2)
        self.assertGreater(top_agents[0]["fair_score"], top_agents[1]["fair_score"])

    def test_stage_c_skips_offline_and_missing_endpoint(self) -> None:
        snapshot = {
            "snapshot_id": "snap3",
            "generated_at": "2026-03-26T10:00:00Z",
            "agents": [
                {
                    "agent_id": 1,
                    "name": "Offline",
                    "display_name_cn": "Offline",
                    "agent_code": "agent-offline",
                    "agent_fqdn": "agent-offline.agent.weather.cn",
                    "routing_fqdn": "weather.cn",
                    "endpoint": "http://offline.local/invoke",
                    "provider": "offline.local",
                    "status": "offline",
                    "last_heartbeat_at": "2026-03-26T10:00:00Z",
                    "tags": ["weather.query"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "exposure_count_agent": 0,
                    "mode": "simulated",
                    "protocol": "http_json",
                },
                {
                    "agent_id": 2,
                    "name": "Missing",
                    "display_name_cn": "Missing",
                    "agent_code": "agent-missing",
                    "agent_fqdn": "agent-missing.agent.weather.cn",
                    "routing_fqdn": "weather.cn",
                    "endpoint": "",
                    "provider": "missing.local",
                    "status": "online",
                    "last_heartbeat_at": "2026-03-26T10:00:00Z",
                    "tags": ["weather.query"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "exposure_count_agent": 0,
                    "mode": "simulated",
                    "protocol": "http_json",
                },
                {
                    "agent_id": 3,
                    "name": "Ready",
                    "display_name_cn": "Ready",
                    "agent_code": "agent-ready",
                    "agent_fqdn": "agent-ready.agent.weather.cn",
                    "routing_fqdn": "weather.cn",
                    "endpoint": "http://ready.local/invoke",
                    "provider": "ready.local",
                    "status": "online",
                    "last_heartbeat_at": "2026-03-26T10:00:00Z",
                    "tags": ["weather.query"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "exposure_count_agent": 0,
                    "mode": "simulated",
                    "protocol": "http_json",
                },
            ],
        }
        result = select_agents_for_subtasks(
            subtasks=[{"need": "weather", "routing_fqdn": "weather.cn", "role": "primary"}],
            registry_snapshot=snapshot,
            resolver=self.resolver,
            top_k=3,
            config=StageCConfig(),
        )
        trace = result["selection_trace"]["groups"][0]
        self.assertEqual(result["groups"][0]["agents"][0]["agent_id"], 3)
        self.assertEqual(trace["filtered_out_reasons"]["status_offline"], 1)
        self.assertEqual(trace["filtered_out_reasons"]["endpoint_missing"], 1)


if __name__ == "__main__":
    unittest.main()
