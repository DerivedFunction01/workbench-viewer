#!/usr/bin/env bun
// test-viewport.ts — the visual-viewport shell sizing
// (client/src/lib/viewport.ts, phone scroll hardening)
// against fake style targets and viewport shapes. Every
// case asserts the contract the shell relies on: the
// property name, the floored value, sync following
// updates, a missing viewport writing nothing (the CSS
// 100dvh fallback governs), and clear restoring it.
//
// Usage: bun viewer/tools/test-viewport.ts
// Exit 1 on any failure.

import {
  APP_HEIGHT_PROPERTY,
  type AppHeightStyleTarget,
  appHeightValue,
  clearAppHeight,
  syncAppHeight,
} from "../client/src/lib/viewport";

let failures = 0;
function check(name: string, ok: boolean, detail = "") {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

class FakeStyle implements AppHeightStyleTarget {
  values = new Map<string, string>();
  setProperty(name: string, value: string): void {
    this.values.set(name, value);
  }
  removeProperty(name: string): void {
    this.values.delete(name);
  }
}

check(
  "the property is the one the shell consumes",
  APP_HEIGHT_PROPERTY === "--wb-app-height",
  APP_HEIGHT_PROPERTY,
);

check(
  "values floor, so the shell never exceeds the visible box",
  appHeightValue(663.9) === "663px" && appHeightValue(664) === "664px",
  `${appHeightValue(663.9)} / ${appHeightValue(664)}`,
);

const synced = new FakeStyle();
check(
  "sync writes the viewport height and reports it wrote",
  syncAppHeight(synced, { height: 500.4 }) === true &&
    synced.values.get(APP_HEIGHT_PROPERTY) === "500px",
  JSON.stringify([...synced.values.entries()]),
);

check(
  "sync follows viewport updates (resize + scroll)",
  syncAppHeight(synced, { height: 420 }) === true &&
    synced.values.get(APP_HEIGHT_PROPERTY) === "420px",
  JSON.stringify([...synced.values.entries()]),
);

const absent = new FakeStyle();
check(
  "a null viewport writes nothing — the CSS fallback governs",
  syncAppHeight(absent, null) === false && absent.values.size === 0,
  JSON.stringify([...absent.values.entries()]),
);
check(
  "an undefined viewport writes nothing either",
  syncAppHeight(absent, undefined) === false && absent.values.size === 0,
  JSON.stringify([...absent.values.entries()]),
);

clearAppHeight(synced);
check(
  "clear removes the property, restoring the fallback",
  synced.values.size === 0,
  JSON.stringify([...synced.values.entries()]),
);

console.log(`test-viewport: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
