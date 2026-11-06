import { evidence, type RootEvidence } from "./root-evidence.js";

export interface SchemaParityInput {
  expectedProjectRef: string | null;
  observedProjectRef: string | null;
  expectedTables: string[];
  observedTables: string[] | null;
  migrationVersion?: string | null;
  expectedMigrationVersion?: string | null;
}

/**
 * PostgREST connectivity is not schema parity. Zero exposed tables is
 * inconclusive unless explicit database inspection proves the schema is empty.
 */
export function evaluateSchemaParity(input: SchemaParityInput): {
  status: "pass" | "fail" | "unknown";
  checks: RootEvidence[];
} {
  const checks: RootEvidence[] = [];
  const projectKnown = Boolean(input.expectedProjectRef && input.observedProjectRef);
  checks.push(evidence(
    "supabase.project_ref",
    !projectKnown ? "unknown" : input.expectedProjectRef === input.observedProjectRef ? "pass" : "fail",
    { expected: input.expectedProjectRef, observed: input.observedProjectRef },
    !projectKnown ? "Expected or observed project ref is missing" : undefined,
  ));

  if (input.observedTables === null) {
    checks.push(evidence("supabase.schema", "unknown", undefined, "Schema inspection did not return table metadata"));
  } else {
    const missing = input.expectedTables.filter((table) => !input.observedTables!.includes(table));
    checks.push(evidence(
      "supabase.tables",
      missing.length === 0 ? "pass" : "fail",
      { expected: input.expectedTables, observed: input.observedTables, missing },
      missing.length ? "Expected tables are missing" : undefined,
    ));
  }

  if (input.expectedMigrationVersion || input.migrationVersion) {
    const known = Boolean(input.expectedMigrationVersion && input.migrationVersion);
    checks.push(evidence(
      "supabase.migrations",
      !known ? "unknown" : input.expectedMigrationVersion === input.migrationVersion ? "pass" : "fail",
      { expected: input.expectedMigrationVersion, observed: input.migrationVersion },
      !known ? "Migration version evidence is incomplete" : undefined,
    ));
  } else {
    checks.push(evidence("supabase.migrations", "unknown", undefined, "Migration inspection is not configured"));
  }

  const status = checks.some((check) => check.status === "fail")
    ? "fail"
    : checks.some((check) => check.status === "unknown")
      ? "unknown"
      : "pass";
  return { status, checks };
}

