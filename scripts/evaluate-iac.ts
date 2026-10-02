import program from "../.railway/railway";
import { createRailwayContext, RAILWAY_GRAPH_VERSION, validateGraph } from "railway/iac";

const definition = program(createRailwayContext({ environment: "offline-verification" }));
const resources = definition.resources;
const edges = resources.flatMap((resource) =>
  resource.type === "service"
    ? Object.values(resource.volumeAttachments ?? {}).map((attachment) => ({
      from: resource.address, to: attachment.volume, type: "mount", key: attachment.mountPath,
    }))
    : [],
);
const graph = { version: RAILWAY_GRAPH_VERSION, resources, edges };
const diagnostics = validateGraph(graph);
if (diagnostics.length) throw new Error(diagnostics.join("; "));
process.stdout.write(JSON.stringify({ evaluation: "offline-sdk", graph }) + "\n");
