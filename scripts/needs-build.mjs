// Says whether the built site (build/, the admin page included) is out of date, so start.cmd and public.cmd only
// rebuild when something changed.
// Exit code 1 means a build is needed; 0 means the build is current.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/** When a file, or anything inside a folder, was last changed. 0 if it is not there. */
function lastChanged(target) {
	const stat = fs.statSync(target, { throwIfNoEntry: false });
	if (!stat) return 0;
	if (!stat.isDirectory()) return stat.mtimeMs;
	return Math.max(0, ...fs.readdirSync(target).map((name) => lastChanged(path.join(target, name))));
}

// Everything the build is made from.
const shared = ['package.json', 'package-lock.json', 'components.json'];
const builds = [
	{ output: 'build/index.html', sources: ['src', 'static', 'vite.config.ts', 'tsconfig.json', ...shared] }
];
const current = builds.every(({ output, sources }) => {
	const changed = Math.max(...sources.map((name) => lastChanged(path.join(root, name))));
	const built = lastChanged(path.join(root, output));
	return built && built >= changed;
});
process.exit(current ? 0 : 1);
