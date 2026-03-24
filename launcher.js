const { spawnSync, spawn } = require('child_process');

console.log("=================================================");
console.log("       Starting OpenClaw Agent and UI...        ");
console.log("=================================================");
console.log("");
console.log("[1/3] Starting OpenClaw Gateway Service in the background...");
// Detached spawn so it runs independently in its own hidden terminal
const gateway = spawn('cmd', ['/c', 'openclaw gateway run'], { detached: false, stdio: 'inherit' });

console.log("[2/3] Starting Python FastAPI Backend Engine on Port 8000...");
const backend = spawn('python', ['-m', 'uvicorn', 'main:app', '--port', '8000', '--host', '127.0.0.1'], { cwd: process.cwd() + '/backend', stdio: 'inherit' });

console.log("Waiting 5 seconds for OpenClaw and Backend to initialize...");
Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 5000);

console.log("[3/3] Starting Next.js UI (http://localhost:3000)...");
spawnSync('npm', ['run', 'dev'], { stdio: 'inherit', shell: true });
