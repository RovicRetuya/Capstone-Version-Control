// Runs the end-to-end checks: starts both servers, runs the test files one after another, stops the servers.
//
//   npm run test:e2e                    every file, against a fresh build of the app
//   npm run test:e2e -- wording errors  only those files
//   npm run test:e2e -- --dev           against the developer server instead of the build
//
// The accounts the tests create go to a scratch database in tests/.tmp, never to the real one.
// The tests read the saved products in the original app's defaketive.db; they do not write to it.
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
// The original app: DEFAKETIVE_ORIGINAL, else its folder beside this project, else backend/ (this repo's own copy).
const beside = path.resolve(root, '../Capstone-Version-Control-Version-1.1');
const original =
	process.env.DEFAKETIVE_ORIGINAL || (fs.existsSync(path.join(beside, 'webapp.py')) ? beside : path.join(root, 'backend'));
const python = path.join(original, '.venv', 'Scripts', 'python.exe');
const vite = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js');
const scratch = path.join(root, 'tests', '.tmp');
const APP = 'http://localhost:5173';
const API = 'http://127.0.0.1:5000';

const ALL = [
	'links', 'flow', 'scan-flow', 'accounts', 'database', 'features', 'guest', 'lock', 'wording', 'errors',
	'targets', 'report-flow', 'round10', 'brand', 'a11y', 'a11y-new', 'a11y-dialogs', 'gallery', 'extension', 'extension-browser',
	'uiux', 'admin', 'tweaks'
];
const args = process.argv.slice(2);
const dev = args.includes('--dev');
const wanted = args.filter((arg) => !arg.startsWith('--'));
const unknown = wanted.filter((name) => !ALL.includes(name));
if (unknown.length) {
	console.error(`No such test file: ${unknown.join(', ')}\nChoose from: ${ALL.join(', ')}`);
	process.exit(2);
}
const suites = wanted.length ? wanted : ALL;

function stopWith(message) {
	console.error(message);
	process.exit(2);
}
if (!fs.existsSync(python)) stopWith(`The original app's Python was not found at ${python}.\nSet DEFAKETIVE_ORIGINAL to the original app's folder.`);
if (!fs.existsSync(path.join(root, 'node_modules', 'playwright-core'))) stopWith('The test packages are not installed. Run "npm install" first.');

const portBusy = (port, host) =>
	new Promise((resolve) => {
		const socket = net.connect({ port, host });
		socket.once('connect', () => (socket.destroy(), resolve(true)));
		socket.once('error', () => resolve(false));
		socket.setTimeout(1500, () => (socket.destroy(), resolve(false)));
	});
// Never take over, or stop, an app that is already running.
if ((await portBusy(5000, '127.0.0.1')) || (await portBusy(5173, 'localhost'))) {
	stopWith('Port 5000 or 5173 is in use. Close the app (and any other test run) first, then try again.');
}

fs.mkdirSync(scratch, { recursive: true });
fs.mkdirSync(path.join(here, 'shots'), { recursive: true });
const children = [];
function start(command, commandArgs, options, logName) {
	const log = fs.openSync(path.join(scratch, logName), 'w');
	const child = spawn(command, commandArgs, { ...options, stdio: ['ignore', log, log], windowsHide: true });
	children.push(child);
	return child;
}
function stopAll() {
	for (const child of children.splice(0)) {
		if (child.exitCode !== null || !child.pid) continue;
		// The whole process tree: the servers start helpers of their own.
		if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
		else child.kill('SIGTERM');
	}
}
process.on('exit', stopAll);
process.on('SIGINT', () => process.exit(130));

async function answers(url) {
	try {
		return (await fetch(url, { signal: AbortSignal.timeout(3000) })).ok;
	} catch {
		return false;
	}
}
async function waitFor(url, what, seconds) {
	const deadline = Date.now() + seconds * 1000;
	while (Date.now() < deadline) {
		if (await answers(url)) return;
		await new Promise((resolve) => setTimeout(resolve, 1000));
	}
	stopWith(`${what} did not answer within ${seconds} seconds. See the logs in tests/.tmp.`);
}

console.log('Starting the server (the original app with a scratch accounts database)...');
start(python, [path.join(root, 'server.py')], {
	cwd: original,
	env: { ...process.env, DEFAKETIVE_ACCOUNTS_DB: path.join(scratch, 'accounts-test.db') }
}, 'server.log');

if (dev) {
	console.log('Starting the developer server...');
	start(process.execPath, [vite, 'dev', '--port', '5173', '--strictPort'], { cwd: root }, 'app.log');
} else {
	console.log('Building the app...');
	const build = spawnSync(process.execPath, [vite, 'build'], { cwd: root, encoding: 'utf8' });
	if (build.status !== 0) {
		console.error(build.stdout?.slice(-3000), build.stderr?.slice(-3000));
		stopWith('The build failed, so no tests were run.');
	}
	console.log('Serving the builds...');
	start(process.execPath, [vite, 'preview', '--port', '5173', '--strictPort'], { cwd: root }, 'app.log');
}
await waitFor(`${API}/api/saved/products`, 'The server', 120);
await waitFor(`${APP}/`, 'The app', 120);

function run(name) {
	return new Promise((resolve) => {
		const child = spawn(process.execPath, [path.join(here, `${name}.mjs`)], {
			cwd: root,
			env: { ...process.env, BASE: APP },
			windowsHide: true
		});
		let output = '';
		child.stdout.on('data', (chunk) => (output += chunk));
		child.stderr.on('data', (chunk) => (output += chunk));
		const timer = setTimeout(() => {
			output += '\nFAIL  this file did not finish within 10 minutes';
			if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
			else child.kill('SIGKILL');
		}, 10 * 60 * 1000);
		child.on('close', (code) => {
			clearTimeout(timer);
			resolve({ code, lines: output.split(/\r?\n/) });
		});
	});
}
// Most files print PASS/FAIL lines. The accessibility sweeps and the screenshot gallery report differently.
function judge(name, { code, lines }) {
	if (name.startsWith('a11y')) {
		const clean = lines.some((line) => line.includes('No accessibility problems found by axe.'));
		const problems = lines.filter((line) => /problem\(s\)|^\s+- \[/.test(line));
		return { passed: lines.filter((line) => /\sok$/.test(line)).length, failed: clean ? 0 : Math.max(1, problems.length), detail: clean ? [] : problems };
	}
	if (name === 'gallery') {
		const problems = lines.filter((line) => /!!|\[pageerror\]/.test(line));
		const failed = problems.length || code ? Math.max(1, problems.length) : 0;
		return { passed: failed ? 0 : 1, failed, detail: problems };
	}
	const failures = lines.filter((line) => line.startsWith('FAIL'));
	const crashed = code !== 0 && !failures.length;
	return {
		passed: lines.filter((line) => line.startsWith('PASS')).length,
		failed: failures.length + (crashed ? 1 : 0),
		detail: crashed ? lines.filter((line) => line.trim()).slice(-12) : failures
	};
}

if (dev) {
	// The developer server prepares pages the first time they are asked for; let it do that before anything counts.
	console.log('Warming up the developer server...');
	await run('links');
	await new Promise((resolve) => setTimeout(resolve, 6000));
}

console.log(`\nRunning ${suites.length} test file(s) against ${dev ? 'the developer server' : 'the built app'}:\n`);
let passed = 0;
let failed = 0;
for (const name of suites) {
	const started = Date.now();
	const result = judge(name, await run(name));
	passed += result.passed;
	failed += result.failed;
	const seconds = Math.round((Date.now() - started) / 1000);
	console.log(`${result.failed ? 'FAIL' : 'ok  '}  ${name.padEnd(13)} ${String(result.passed).padStart(3)} passed${result.failed ? `, ${result.failed} failed` : ''}  (${seconds}s)`);
	for (const line of result.detail) console.log(`        ${line}`);
}
stopAll();
console.log(`\n${passed} checks passed, ${failed} failed.`);
process.exit(failed ? 1 : 0);
