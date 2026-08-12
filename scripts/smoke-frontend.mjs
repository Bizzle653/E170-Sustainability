import {spawn} from "node:child_process";

const port = 3100;
const baseUrl = `http://127.0.0.1:${port}`;
const server = spawn(
  process.execPath,
  ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", String(port)],
  {stdio: "inherit", env: {...process.env, NODE_ENV: "production"}},
);

async function waitForServer() {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
    } catch {
      // The server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("Next.js did not become ready for the smoke test");
}

async function assertPage(path, expectedText) {
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  const body = await response.text();
  if (!body.includes(expectedText)) throw new Error(`${path} did not contain ${expectedText}`);
}

try {
  await waitForServer();
  await assertPage("/", "Green Canopy");
  await assertPage("/classification-updates", "Every label change is public");
  await assertPage("/agent-status", "Classification coverage is measurable");
  console.log("frontend smoke: passed");
} finally {
  server.kill();
}
