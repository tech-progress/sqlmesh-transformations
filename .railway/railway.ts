import { defineRailway, github, group, project, service, volume } from "railway/iac";

const repository = process.env.TEMPLATE_SOURCE_REPO ?? "tech-progress/sqlmesh-transformations";
if (!repository || !/^[\w.-]+\/[\w.-]+$/.test(repository)) {
  throw new Error("Set TEMPLATE_SOURCE_REPO to the real owner/repository; no standalone repository is assumed.");
}
const branch = process.env.TEMPLATE_SOURCE_BRANCH ?? "release-v1";
if (branch.includes("/")) throw new Error("Use a slash-free Railway release branch.");
const rootDirectory = process.env.TEMPLATE_SOURCE_ROOT ?? "/";
const watchRoot = rootDirectory.replace(/^\/+|\/+$/g, "");
const postgresImage = "postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea";

export default defineRailway(() => {
  const stateData = volume("State Data", { sizeMB: 5_000 });
  const warehouseData = volume("Warehouse Data", { sizeMB: 5_000 });
  const state = service("SQLMesh State", {
    source: { image: postgresImage },
    volumeMounts: { "/var/lib/postgresql/data": stateData },
    env: {
      POSTGRES_DB: "sqlmesh_state", POSTGRES_USER: "sqlmesh",
      POSTGRES_PASSWORD: (process.env.TEMPLATE_STATE_PASSWORD ?? "${{secret(32)}}"),
      PGDATA: "/var/lib/postgresql/data/pgdata",
    },
    deploy: { restartPolicyType: "ON_FAILURE" },
  });
  const warehouse = service("SQLMesh Warehouse", {
    source: { image: postgresImage },
    volumeMounts: { "/var/lib/postgresql/data": warehouseData },
    env: {
      POSTGRES_DB: "warehouse", POSTGRES_USER: "sqlmesh",
      POSTGRES_PASSWORD: (process.env.TEMPLATE_WAREHOUSE_PASSWORD ?? "${{secret(32)}}"),
      PGDATA: "/var/lib/postgresql/data/pgdata",
    },
    deploy: { restartPolicyType: "ON_FAILURE" },
  });
  const runner = service("SQLMesh Runner", {
    source: github(repository, { branch, rootDirectory }),
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile", watchPatterns: [watchRoot ? `/${watchRoot}/**` : "/**"] },
    start: "./start.sh",
    deploy: { cronSchedule: "0 * * * *", restartPolicyType: "NEVER" },
    env: {
      PYTHONPATH: "/app",
      STATE_HOST: "${{SQLMesh State.RAILWAY_PRIVATE_DOMAIN}}", STATE_PORT: "5432",
      STATE_DATABASE: "${{SQLMesh State.POSTGRES_DB}}", STATE_USER: "${{SQLMesh State.POSTGRES_USER}}",
      STATE_PASSWORD: "${{SQLMesh State.POSTGRES_PASSWORD}}", STATE_SSLMODE: "prefer",
      WAREHOUSE_HOST: "${{SQLMesh Warehouse.RAILWAY_PRIVATE_DOMAIN}}", WAREHOUSE_PORT: "5432",
      WAREHOUSE_DATABASE: "${{SQLMesh Warehouse.POSTGRES_DB}}", WAREHOUSE_USER: "${{SQLMesh Warehouse.POSTGRES_USER}}",
      WAREHOUSE_PASSWORD: "${{SQLMesh Warehouse.POSTGRES_PASSWORD}}", WAREHOUSE_SSLMODE: "prefer",
    },
  });
  return project("SQLMesh transformations", {
    resources: [group("Transformations", [runner]), group("Storage", [state, stateData, warehouse, warehouseData])],
  });
});
