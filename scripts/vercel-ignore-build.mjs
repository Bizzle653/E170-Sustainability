const operationalState = "backend/data/classification_agent_state.json";
const repository = "highGround-helloThere/E170-Sustainability";

try {
  const commitSha = process.env.VERCEL_GIT_COMMIT_SHA;
  if (!commitSha) throw new Error("VERCEL_GIT_COMMIT_SHA is unavailable");
  const response = await fetch(`https://api.github.com/repos/${repository}/commits/${commitSha}`, {
    headers: {Accept: "application/vnd.github+json", "User-Agent": "green-canopy-vercel-ignore"},
    signal: AbortSignal.timeout(5_000),
  });
  if (!response.ok) throw new Error(`GitHub commit lookup returned HTTP ${response.status}`);
  const payload = await response.json();
  const changed = Array.isArray(payload.files)
    ? payload.files.map((item) => item.filename).filter(Boolean)
    : [];
  const stateOnly = changed.length > 0 && changed.every((item) => item === operationalState);
  console.log(stateOnly ? "Skipping state-only deployment." : `Building changes in: ${changed.join(", ")}`);
  process.exitCode = stateOnly ? 0 : 1;
} catch (error) {
  // Build on any lookup failure rather than risk skipping a meaningful change.
  console.log(`Could not determine changed files; continuing build: ${error instanceof Error ? error.message : error}`);
  process.exitCode = 1;
}
