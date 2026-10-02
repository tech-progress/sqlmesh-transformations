import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("template_contract", ROOT / "scripts/template-contract.py")
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


class TemplateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(Path(os.environ["SQLMESH_TEST_GRAPH"]).read_text())

    def contaminated(self):
        return {"data": {"template": {"name": "Seed template", "serializedConfig": {
            "services": {
                name: {
                    "name": name,
                    "source": {"repo": "stale/seed", "image": "nginx:latest", "branch": "main", "rootDirectory": "/wrong"},
                    "build": {"builder": "NIXPACKS", "buildCommand": "wrong"},
                    "deploy": {"cronSchedule": "* * * * *", "restartPolicyType": "ALWAYS", "startCommand": "sleep infinity", "healthcheckPath": "/"},
                    "networking": {"serviceDomains": {"public": {"port": 80}}, "tcpProxies": {"public": {"port": 5432}}},
                    "variables": {"AUTO_APPLY": {"defaultValue": "true"}, "STATE_PASSWORD": {"value": "resolved-secret-leftover"}},
                    "volumeMounts": {"shared-seed": {"mountPath": "/wrong", "sizeMB": 1}},
                }
                for name in ("SQLMesh Runner", "SQLMesh State", "SQLMesh Warehouse")
            }
        }}}}

    def test_contamination_fails_then_restores_idempotently(self):
        draft = self.contaminated()
        with self.assertRaises(ValueError):
            CONTRACT.audit(draft, self.graph)
        repaired = CONTRACT.restore(draft, self.graph)
        CONTRACT.audit(repaired, self.graph)
        self.assertEqual(repaired, CONTRACT.restore(repaired, self.graph))
        services = repaired["data"]["template"]["serializedConfig"]["services"]
        self.assertEqual(services["SQLMesh Runner"]["deploy"]["cronSchedule"], "0 * * * *")
        self.assertEqual(services["SQLMesh Runner"]["deploy"]["restartPolicyType"], "NEVER")
        self.assertNotIn("healthcheckPath", services["SQLMesh Runner"]["deploy"])
        self.assertEqual(services["SQLMesh Runner"]["volumeMounts"], {})
        self.assertNotIn("resolved-secret-leftover", json.dumps(repaired))

    def test_every_contract_dimension_is_audited(self):
        repaired = CONTRACT.restore(self.contaminated(), self.graph)
        for field in ("source", "build", "deploy", "networking", "variables", "volumeMounts"):
            with self.subTest(field=field):
                corrupted = copy.deepcopy(repaired)
                corrupted["data"]["template"]["serializedConfig"]["services"]["SQLMesh Runner"][field] = {"wrong": "value"}
                with self.assertRaises(ValueError):
                    CONTRACT.audit(corrupted, self.graph)

    def test_unique_captured_volume_keys_are_preserved(self):
        draft = self.contaminated()
        services = draft["data"]["template"]["serializedConfig"]["services"]
        services["SQLMesh State"]["volumeMounts"] = {"captured-state-key": {"mountPath": "/wrong", "sizeMB": 1}}
        services["SQLMesh Warehouse"]["volumeMounts"] = {"captured-warehouse-key": {"mountPath": "/wrong", "sizeMB": 1}}
        repaired = CONTRACT.restore(draft, self.graph)
        CONTRACT.audit(repaired, self.graph)
        services = repaired["data"]["template"]["serializedConfig"]["services"]
        self.assertEqual(set(services["SQLMesh State"]["volumeMounts"]), {"captured-state-key"})
        self.assertEqual(set(services["SQLMesh Warehouse"]["volumeMounts"]), {"captured-warehouse-key"})

    def test_graph_edges_and_attachments_are_independently_audited(self):
        CONTRACT.audit_graph(self.graph)
        graph = copy.deepcopy(self.graph)
        graph["graph"]["edges"][0]["to"] = graph["graph"]["edges"][1]["to"]
        with self.assertRaises(ValueError):
            CONTRACT.audit_graph(graph)
        graph = copy.deepcopy(self.graph)
        runner = CONTRACT.desired_services(graph)["SQLMesh Runner"]
        runner["volumeAttachments"] = {"State Data": {"volume": "volume.State Data", "mountPath": "/app"}}
        with self.assertRaises(ValueError):
            CONTRACT.audit_graph(graph)

    def test_offline_cli_rejects_contamination_then_restores(self):
        with tempfile.TemporaryDirectory(prefix="sqlmesh-draft-offline-") as directory:
            directory = Path(directory)
            draft = directory / "draft.json"
            repaired = directory / "repaired.json"
            draft.write_text(json.dumps(self.contaminated()))
            result = subprocess.run([str(ROOT / "scripts/audit-template.sh"), str(draft), os.environ["SQLMESH_TEST_GRAPH"]], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            subprocess.run([str(ROOT / "scripts/restore-template-draft.sh"), str(draft), os.environ["SQLMESH_TEST_GRAPH"], "--output", str(repaired)], check=True)
            subprocess.run([str(ROOT / "scripts/audit-template.sh"), str(repaired), os.environ["SQLMESH_TEST_GRAPH"]], check=True)
            self.assertNotIn("resolved-secret-leftover", repaired.read_text())

    def test_extra_or_missing_service_fails_closed(self):
        draft = self.contaminated()
        draft["data"]["template"]["serializedConfig"]["services"].pop("SQLMesh State")
        with self.assertRaises(ValueError):
            CONTRACT.restore(draft, self.graph)

    def test_source_is_configurable_and_images_have_no_git_leftovers(self):
        repaired = CONTRACT.restore(self.contaminated(), self.graph)
        services = repaired["data"]["template"]["serializedConfig"]["services"]
        expected = CONTRACT.desired_services(self.graph)["SQLMesh Runner"]["source"].copy()
        expected.pop("type")
        self.assertEqual(services["SQLMesh Runner"]["source"], expected)
        for name in ("SQLMesh State", "SQLMesh Warehouse"):
            self.assertEqual(set(services[name]["source"]), {"image"})


if __name__ == "__main__":
    unittest.main()
