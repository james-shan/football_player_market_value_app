import "server-only";
import path from "node:path";
import fs from "node:fs";
import {
  DuckDBInstance,
  type DuckDBConnection,
  type DuckDBValue,
} from "@duckdb/node-api";

const DUCKDB_PATH = path.join(
  process.cwd(),
  "data",
  "merged",
  "player_analytics.duckdb",
);

declare global {
  // eslint-disable-next-line no-var
  var __duckdbConn: Promise<DuckDBConnection> | undefined;
}

async function createConnection(): Promise<DuckDBConnection> {
  if (!fs.existsSync(DUCKDB_PATH)) {
    throw new Error(
      `DuckDB file not found at ${DUCKDB_PATH}. Build it with scripts/build_player_analytics_duckdb.py.`,
    );
  }
  const instance = await DuckDBInstance.create(DUCKDB_PATH, {
    access_mode: "READ_ONLY",
  });
  return await instance.connect();
}

export function getConnection(): Promise<DuckDBConnection> {
  if (!globalThis.__duckdbConn) {
    globalThis.__duckdbConn = createConnection();
  }
  return globalThis.__duckdbConn;
}

function normalize(value: unknown): unknown {
  if (typeof value === "bigint") {
    return Number(value);
  }
  if (Array.isArray(value)) {
    return value.map(normalize);
  }
  if (value && typeof value === "object" && (value as object).constructor === Object) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = normalize(v);
    }
    return out;
  }
  return value;
}

/**
 * Runs SQL and returns plain objects with primitive JS values.
 * BigInt is coerced to Number (all values in this dataset are safe integers).
 */
export async function query<T = Record<string, unknown>>(
  sql: string,
  params: DuckDBValue[] = [],
): Promise<T[]> {
  const conn = await getConnection();
  const reader = params.length
    ? await conn.runAndReadAll(sql, params)
    : await conn.runAndReadAll(sql);
  const rows = reader.getRowObjectsJS();
  return normalize(rows) as T[];
}
