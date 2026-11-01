// Opens DeFaketive in the browser once both servers answer, so the first page never loads half-ready.
//
//   node scripts/wait-and-open.mjs               wait (up to 90 seconds), then open the browser
//   node scripts/wait-and-open.mjs --if-running  do not wait: open the browser only if the app is already
//                                                running. Exit code 0 = it was and is now open, 1 = nothing
//                                                is running, 2 = only one of the two ports answers.
import { spawn } from 'node:child_process';

const APP = 'http://localhost:5173/enter';
const SERVER = 'http://127.0.0.1:5000/api/auth/me';
const WAIT_SECONDS = 90;

async function answers(url) {
	try {
		// Any answer counts, also "not signed in": it means the server is up.
		await fetch(url, { signal: AbortSignal.timeout(2500) });
		return true;
	} catch {
		return false;
	}
}
function openBrowser() {
	if (process.platform === 'win32') spawn('cmd', ['/c', 'start', '', APP], { detached: true, stdio: 'ignore' }).unref();
	else spawn(process.platform === 'darwin' ? 'open' : 'xdg-open', [APP], { detached: true, stdio: 'ignore' }).unref();
}

if (process.argv.includes('--if-running')) {
	const [app, server] = await Promise.all([answers(APP), answers(SERVER)]);
	if (app && server) {
		openBrowser();
		process.exit(0);
	}
	process.exit(app || server ? 2 : 1);
}

const deadline = Date.now() + WAIT_SECONDS * 1000;
while (Date.now() < deadline) {
	const [app, server] = await Promise.all([answers(APP), answers(SERVER)]);
	if (app && server) {
		console.log(`DeFaketive is ready. Opening ${APP} ...`);
		openBrowser();
		process.exit(0);
	}
	await new Promise((resolve) => setTimeout(resolve, 1000));
}
console.log(`DeFaketive did not answer within ${WAIT_SECONDS} seconds.`);
console.log('Look at the "DeFaketive server" window for an error, then close both windows and start again.');
process.exit(1);
