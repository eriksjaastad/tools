import { spawn } from "node:child_process";
import os from "node:os";
import path from "node:path";

const log = console;
const STARTUP_TIMEOUT_MS = 30_000;

const handleModelHealthStartup = async (event) => {
  if (event.type !== "gateway" || event.action !== "startup") return;

  const home = os.homedir();
  const scriptPath = path.join(home, ".openclaw", "workspace", "projects", "tools", "check_models.sh");

  await new Promise((resolve) => {
    const child = spawn("/bin/bash", [scriptPath], {
      cwd: path.dirname(scriptPath),
      env: { ...process.env, HOME: home },
      stdio: "pipe",
    });

    let stdout = "";
    let stderr = "";

    child.stdout?.on("data", (data) => {
      stdout += data.toString();
    });

    child.stderr?.on("data", (data) => {
      stderr += data.toString();
    });

    const timer = setTimeout(() => {
      stderr += `Timed out after ${STARTUP_TIMEOUT_MS}ms while running ${scriptPath}\n`;
      child.kill("SIGTERM");
      setTimeout(() => child.kill("SIGKILL"), 2_000).unref();
    }, STARTUP_TIMEOUT_MS);

    child.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0) {
        log.info(`[model-health-startup] check_models.sh completed\n${stdout.trim()}`);
      } else {
        log.error(`[model-health-startup] check_models.sh failed (${code}) at ${scriptPath}\n${stderr.trim()}`);
      }
      resolve();
    });

    child.on("error", (err) => {
      clearTimeout(timer);
      log.error(`[model-health-startup] spawn failed for ${scriptPath}: ${err.message}`);
      resolve();
    });
  });
};

export default handleModelHealthStartup;
