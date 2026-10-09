import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import openapiTS, { astToString } from "openapi-typescript";
import Ajv from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import standaloneCode from "ajv/dist/standalone/index.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const dir = path.join(root, "frontend/src/lib/api/generated");
const check = process.argv.includes("--check");
const temporary = path.join(root, "frontend/.openapi-export.tmp.json");
const exported = spawnSync("uv", ["run", "--offline", "--frozen", "python", "scripts/export_openapi.py", "--output", temporary], {
  cwd: path.join(root, "backend"), stdio: "inherit",
  env: { ...process.env, UV_CACHE_DIR: process.env.UV_CACHE_DIR ?? "/tmp/reviewer-uv-cache" },
});
if (exported.status !== 0) process.exit(exported.status ?? 1);
const full = await fs.readFile(temporary, "utf8");
await fs.unlink(temporary);
const schema = JSON.parse(full);
const pilots = [
  ["agentTurn", "/agent/turns", "post"],
  ["confirmProposal", "/agent/proposals/{proposal_id}/confirm", "post"],
  ["rejectProposal", "/agent/proposals/{proposal_id}/reject", "post"],
  ["strategyPatch", "/strategies/{strategy_id}", "patch"],
  ["attention", "/dashboard/attention", "get"],
  ["dailyReview", "/dashboard/daily-review", "get"],
];
const schemas = schema.components.schemas;
const used = new Set();
function visit(value) {
  if (!value || typeof value !== "object") return;
  if (value.$ref?.startsWith("#/components/schemas/")) {
    const name = value.$ref.split("/").at(-1);
    if (!used.has(name)) { used.add(name); visit(schemas[name]); }
  }
  for (const item of Object.values(value)) visit(item);
}
const paths = {};
for (const [, route, method] of pilots) {
  paths[route] ??= {};
  paths[route][method] = schema.paths[route][method];
  visit(paths[route][method]);
}
const pilot = { ...schema, paths, components: { ...schema.components,
  schemas: Object.fromEntries([...used].sort().map(name => [name, schemas[name]])) } };
const typeText = astToString(await openapiTS(pilot, { defaultNonNullable: false }));
const rewriteRefs = value => {
  if (Array.isArray(value)) return value.map(rewriteRefs);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key,
    key === "$ref" ? item.replace("#/components/schemas/", "#/$defs/") : rewriteRefs(item)]));
};
const ajv = new Ajv({ strict: false, code: { source: true, esm: true }, coerceTypes: false,
  useDefaults: false, removeAdditional: false, validateFormats: true });
addFormats(ajv);
ajv.addSchema({ $id: "http-contract", $defs: rewriteRefs(pilot.components.schemas) });
const validatorRefs = {};
let client = '// Generated from local FastAPI OpenAPI. Run npm run api:generate.\n' +
  'import type { paths } from "./types";\nimport { validatedFetch } from "../validated-fetch";\n' +
  'import * as validators from "./validators";\n\n';
for (const [name, route, method] of pilots) {
  const op = schema.paths[route][method];
  const response = op.responses['200'].content['application/json'].schema.$ref.split('/').at(-1);
  validatorRefs[name + 'Response'] = `http-contract#/$defs/${response}`;
  const param = route.match(/\{(.+?)\}/)?.[1];
  const hasBody = Boolean(op.requestBody);
  if (hasBody) {
    const body = op.requestBody.content['application/json'].schema.$ref.split('/').at(-1);
    validatorRefs[name + 'Request'] = `http-contract#/$defs/${body}`;
  }
  const opType = `paths[${JSON.stringify(route)}][${JSON.stringify(method)}]`;
  const parameters = [
    ...(param ? [`id: ${opType}["parameters"]["path"][${JSON.stringify(param)}]`] : []),
    ...(hasBody ? [`body: ${opType}["requestBody"]["content"]["application/json"]`] : []),
    ...(op.parameters?.some(p => p.in === 'query') ? [`query?: ${opType}["parameters"]["query"]`] : []),
    'options?: { signal?: AbortSignal; headers?: Record<string, string> }',
  ];
  const routeExpr = param ? '`' + route.replace(`{${param}}`, '${encodeURIComponent(id)}') + '`' : JSON.stringify(route);
  client += `export function ${name}(${parameters.join(', ')}) {\n` +
    `  return validatedFetch<${opType}["responses"][200]["content"]["application/json"]>(${routeExpr}, {\n` +
    `    method: "${method.toUpperCase()}", auth: true, signal: options?.signal, headers: options?.headers,\n` +
    (hasBody ? `    bodyValue: body, requestValidator: validators.${name}Request,\n` : '') +
    (op.parameters?.some(p => p.in === 'query') ? '    query,\n' : '') +
    `    responseValidator: validators.${name}Response,\n  });\n}\n\n`;
}
// AJV emits a root function twice when two endpoints share the same response schema.
// Generate each root once and export explicit aliases for shared contracts.
const uniqueRefs = {};
const namesByRef = new Map();
const aliases = [];
for (const [name, ref] of Object.entries(validatorRefs)) {
  if (namesByRef.has(ref)) aliases.push(`export const ${name} = ${namesByRef.get(ref)};`);
  else { namesByRef.set(ref, name); uniqueRefs[name] = ref; }
}
const validators = standaloneCode(ajv, uniqueRefs) + "\n" + aliases.join("\n") + "\n";
const declarations = '// Generated validators do not coerce, default, or strip values.\n' +
  'import type { ValidateFunction } from "ajv";\n' +
  'import type { components } from "./types";\n' +
  Object.entries(validatorRefs).map(([n, ref]) =>
    `export const ${n}: ValidateFunction<components["schemas"][${JSON.stringify(ref.split('/').at(-1))}]>;`).join('\n') + '\n';
const hash = content => crypto.createHash('sha256').update(content).digest('hex');
const hashes = JSON.stringify({ openapi_sha256: hash(full), pilot_sha256: hash(JSON.stringify(pilot)),
  schemas: Object.fromEntries([...used].sort().map(n => [n, hash(JSON.stringify(schemas[n]))])) }, null, 2) + '\n';
await fs.mkdir(dir, { recursive: true });
for (const [name, content] of Object.entries({ 'openapi.json': full, 'types.ts': typeText,
  'client.ts': client.trimEnd() + '\n', 'validators.js': validators, 'validators.d.ts': declarations, 'hashes.json': hashes })) {
  if (check) {
    if (await fs.readFile(path.join(dir, name), 'utf8').catch(() => '') !== content) {
      console.error(`API schema drift: ${name}. Run npm run api:generate.`); process.exitCode = 1;
    }
  } else await fs.writeFile(path.join(dir, name), content);
}
if (!process.exitCode) console.log(`API ${check ? 'drift check passed' : 'generated'}; full schema SHA256 ${hash(full)}`);
