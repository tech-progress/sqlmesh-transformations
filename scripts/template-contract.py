import argparse
import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read_json(path):
    return json.loads(Path(path).read_text())


def serialized_config(document):
    if "data" in document:
        return document["data"]["template"]["serializedConfig"]
    return document


def desired_services(graph):
    return {resource["name"]: resource for resource in graph["graph"]["resources"] if resource["type"] == "service"}


def audit_graph(document):
    graph = document["graph"]
    services = desired_services(document)
    expected_mounts = {
        "SQLMesh State": "State Data",
        "SQLMesh Warehouse": "Warehouse Data",
    }
    if set(services) != {"SQLMesh Runner", *expected_mounts}:
        raise ValueError("Graph must contain exactly three services")
    volumes = {resource["name"]: resource for resource in graph["resources"] if resource["type"] == "volume"}
    if set(volumes) != set(expected_mounts.values()):
        raise ValueError("Graph requires exactly two independent volumes")
    mount_edges = [edge for edge in graph["edges"] if edge["type"] == "mount"]
    expected_edges = []
    defaults = read_json(ROOT / "template-defaults.json")
    for name, resource in services.items():
        if resource.get("networking") or resource.get("volumeMounts"):
            raise ValueError(f"{name}: unexpected networking or raw volume mounts")
        for key, value in defaults[name].items():
            observed = resource["variables"][key]["value"]
            if key != "POSTGRES_PASSWORD" and observed != value:
                raise ValueError(f"{name}: variable contract differs (redacted)")
        if set(resource["variables"]) != set(defaults[name]):
            raise ValueError(f"{name}: unexpected/missing variables")
        if name in expected_mounts:
            volume_name = expected_mounts[name]
            expected_attachment = {"volume": volumes[volume_name]["address"], "mountPath": "/var/lib/postgresql/data", "volumeConfig": {"sizeMB": 5000}}
            if resource.get("volumeAttachments") != {volume_name: expected_attachment}:
                raise ValueError(f"{name}: incorrect volume attachment")
            if volumes[volume_name]["config"] != {"sizeMB": 5000}:
                raise ValueError(f"{name}: incorrect volume size")
            expected_edges.append({"from": resource["address"], "to": volumes[volume_name]["address"], "type": "mount", "key": "/var/lib/postgresql/data"})
            if resource["source"] != {"type": "image", "image": "postgres:16-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea"}:
                raise ValueError(f"{name}: database image/source mismatch")
        elif resource.get("volumeAttachments"):
            raise ValueError("Runner must not have a volume")
    if sorted(mount_edges, key=lambda edge: edge["from"]) != sorted(expected_edges, key=lambda edge: edge["from"]):
        raise ValueError("Graph must have exactly two mount edges to distinct database volumes")
    runner = services["SQLMesh Runner"]
    if runner["deploy"] != {"startCommand": "./start.sh", "cronSchedule": "0 * * * *", "restartPolicyType": "NEVER"}:
        raise ValueError("Runner must have hourly cron, NEVER restart, and no healthcheck")
    if runner["source"].get("type") != "github" or "image" in runner["source"]:
        raise ValueError("Runner must have exactly the configured GitHub source")
    state_password = services["SQLMesh State"]["variables"]["POSTGRES_PASSWORD"]["value"]
    warehouse_password = services["SQLMesh Warehouse"]["variables"]["POSTGRES_PASSWORD"]["value"]
    if state_password == warehouse_password and state_password != "${{secret(32)}}":
        raise ValueError("Database secrets must be independent")


def restore(document, graph):
    audit_graph(graph)
    result = copy.deepcopy(document)
    config = serialized_config(result)
    desired = desired_services(graph)
    defaults = read_json(ROOT / "template-defaults.json")
    descriptions = read_json(ROOT / "template-descriptions.json")
    volumes = read_json(ROOT / "template-volumes.json")
    names = [service["name"] for service in config["services"].values()]
    if sorted(names) != sorted(desired):
        raise ValueError("Draft must contain exactly the three named SQLMesh services")
    captured_keys = {}
    for actual in config["services"].values():
        if actual["name"] in volumes and len(actual.get("volumeMounts", {})) == 1:
            captured_keys[actual["name"]] = next(iter(actual["volumeMounts"]))
    if len(set(captured_keys.values())) != len(captured_keys):
        captured_keys = {}
    for actual in config["services"].values():
        name = actual["name"]
        resource = desired[name]
        source = resource["source"]
        actual["source"] = {key: value for key, value in source.items() if key != "type"}
        actual.pop("configFile", None)
        if "build" in resource:
            actual["build"] = copy.deepcopy(resource["build"])
        else:
            actual.pop("build", None)
        actual["deploy"] = copy.deepcopy(resource.get("deploy", {}))
        actual["networking"] = {"serviceDomains": {}, "tcpProxies": {}}
        actual["variables"] = {
            key: {"defaultValue": value, "description": descriptions[name][key], "isOptional": False}
            for key, value in defaults[name].items()
        }
        volume = volumes.get(name)
        actual["volumeMounts"] = {} if volume is None else {
            captured_keys.get(name, volume["key"]): {"mountPath": volume["mountPath"], "sizeMB": volume["sizeMB"]}
        }
    if "data" in result:
        result["data"]["template"]["name"] = "SQLMesh transformations"
    return result


def audit(document, graph):
    config = serialized_config(document)
    expected = serialized_config(restore(document, graph))
    if "data" in document and document["data"]["template"].get("name") != "SQLMesh transformations":
        raise ValueError("Template name mismatch")
    for key, actual in config["services"].items():
        canonical = expected["services"][key]
        for field in ("source", "build", "deploy", "networking", "variables", "volumeMounts", "configFile"):
            if actual.get(field) != canonical.get(field):
                raise ValueError(f"{actual['name']}: {field} differs from the reviewed contract (values redacted)")
    mounts = [key for service in config["services"].values() for key in service.get("volumeMounts", {})]
    if len(mounts) != 2 or len(set(mounts)) != 2:
        raise ValueError("Exactly two independent database mounts are required")


def main():
    parser = argparse.ArgumentParser(description="Offline-only serialized draft repair/audit. No network or credentials.")
    parser.add_argument("action", choices=("restore", "audit"))
    parser.add_argument("draft", type=Path)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    document = read_json(arguments.draft)
    graph = read_json(arguments.graph)
    if arguments.action == "restore":
        document = restore(document, graph)
        encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
        if arguments.output:
            arguments.output.write_text(encoded)
        else:
            print(encoded, end="")
    else:
        audit(document, graph)
        print("Offline SQLMesh draft source, cron, defaults, networking, and independent volumes pass")


if __name__ == "__main__":
    main()
