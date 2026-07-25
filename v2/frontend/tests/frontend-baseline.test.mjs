import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

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
