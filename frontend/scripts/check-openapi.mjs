import { access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const openapiPath = path.join(root, "openapi.json");

await access(openapiPath);
console.log("openapi.json present at", openapiPath);
