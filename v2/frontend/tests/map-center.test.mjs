import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_MAP_CENTER, resolveMapViewport } from "../app/map-center.ts";

test("uses the Japan overview when no valid location is available", () => {
  assert.deepEqual(resolveMapViewport([], null), {
    kind: "center",
    center: DEFAULT_MAP_CENTER,
    zoom: 5,
    key: `center:${DEFAULT_MAP_CENTER[0]}:${DEFAULT_MAP_CENTER[1]}:5`,
  });
});

test("keeps the current location as the highest-priority center", () => {
  assert.deepEqual(
    resolveMapViewport([{ latitude: 43.06, longitude: 141.35 }], { latitude: 35.68, longitude: 139.76 }),
    {
      kind: "center",
      center: [35.68, 139.76],
      zoom: 13,
      key: "center:35.68:139.76:13",
    },
  );
});

test("centers a single valid result directly", () => {
  assert.deepEqual(resolveMapViewport([{ latitude: 36.14, longitude: 139.39 }], null), {
    kind: "center",
    center: [36.14, 139.39],
    zoom: 13,
    key: "center:36.14:139.39:13",
  });
});

test("fits multiple results by geographic bounds independent of ordering", () => {
  const places = [
    { latitude: 43.06, longitude: 141.35 },
    { latitude: 26.21, longitude: 127.68 },
    { latitude: 35.68, longitude: 139.76 },
  ];
  const expected = {
    kind: "bounds",
    bounds: [
      [26.21, 127.68],
      [43.06, 141.35],
    ],
    key: "bounds:26.21:127.68:43.06:141.35",
  };

  assert.deepEqual(resolveMapViewport(places, null), expected);
  assert.deepEqual(resolveMapViewport([...places].reverse(), null), expected);
});

test("does not let a dense regional cluster pull the national viewport", () => {
  const tokyoCluster = Array.from({ length: 100 }, () => ({ latitude: 35.68, longitude: 139.76 }));
  const places = [
    ...tokyoCluster,
    { latitude: 43.06, longitude: 141.35 },
    { latitude: 26.21, longitude: 127.68 },
  ];

  assert.deepEqual(resolveMapViewport(places, null), {
    kind: "bounds",
    bounds: [
      [26.21, 127.68],
      [43.06, 141.35],
    ],
    key: "bounds:26.21:127.68:43.06:141.35",
  });
});

test("ignores invalid coordinates when choosing the viewport", () => {
  assert.deepEqual(
    resolveMapViewport(
      [
        { latitude: Number.NaN, longitude: 139.76 },
        { latitude: 36.14, longitude: 139.39 },
      ],
      { latitude: 91, longitude: 139.76 },
    ),
    {
      kind: "center",
      center: [36.14, 139.39],
      zoom: 13,
      key: "center:36.14:139.39:13",
    },
  );
});
