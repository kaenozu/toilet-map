import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const agentGuide = readFileSync(new URL("../../../AGENTS.md", import.meta.url), "utf8");
const v2Readme = readFileSync(new URL("../../README.md", import.meta.url), "utf8");

function majorMinor(version) {
  const match = /^(\d+)\.(\d+)\./.exec(version);
  assert.ok(match, `expected an exact semantic version, received ${version}`);
  return `${match[1]}.${match[2]}`;
}

test("keeps React runtime packages on one supported version", () => {
  assert.equal(packageJson.dependencies.react, packageJson.dependencies["react-dom"]);
});

test("keeps React type packages aligned with the runtime line", () => {
  const runtimeLine = majorMinor(packageJson.dependencies.react);
  assert.equal(majorMinor(packageJson.devDependencies["@types/react"]), runtimeLine);
  assert.equal(majorMinor(packageJson.devDependencies["@types/react-dom"]), runtimeLine);
});

test("pins frontend dependencies to exact versions", () => {
  for (const [name, version] of Object.entries({
    ...packageJson.dependencies,
    ...packageJson.devDependencies,
  })) {
    assert.match(version, /^\d+\.\d+\.\d+$/, `${name} must use an exact version`);
  }
});

test("documents the accepted frontend baseline consistently", () => {
  const nextVersion = packageJson.dependencies.next;
  const reactVersion = packageJson.dependencies.react;
  const typescriptVersion = packageJson.devDependencies.typescript;

  assert.match(
    agentGuide,
    new RegExp(
      `Node\\.js 22 / Next\\.js ${nextVersion.replaceAll(".", "\\.")} / React ${reactVersion.replaceAll(".", "\\.")} / TypeScript`,
    ),
  );
  assert.match(
    v2Readme,
    new RegExp(
      `Node\\.js 22, Next\\.js ${nextVersion.replaceAll(".", "\\.")}, React ${reactVersion.replaceAll(".", "\\.")} and TypeScript ${typescriptVersion.replaceAll(".", "\\.")}`,
    ),
  );
});
