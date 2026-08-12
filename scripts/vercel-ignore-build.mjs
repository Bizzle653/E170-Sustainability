import {execFileSync} from "node:child_process";

const operationalState = "backend/data/classification_agent_state.json";

try {
  const changed = execFileSync("git", ["diff", "--name-only", "HEAD^", "HEAD"], {encoding: "utf8"})
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  const stateOnly = changed.length > 0 && changed.every((item) => item === operationalState);
  process.exit(stateOnly ? 0 : 1);
} catch {
  // If Vercel does not provide the previous commit, build rather than risk
  // skipping a meaningful production change.
  process.exit(1);
}
