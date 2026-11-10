// Makes a copy of the browser extension that reports to a given DeFaketive site, ready to load or to upload.
//
//   node scripts/build-extension.mjs                          -> for http://localhost:5173 (start.cmd)
//   node scripts/build-extension.mjs --site http://127.0.0.1:8080          (public.cmd on this PC)
//   node scripts/build-extension.mjs --site https://defaketive.duckdns.org (the live site; deploy/setup-server.sh
//                                                                           runs it with --download)
//
// Writes dist-extension/ (load it in Chrome: chrome://extensions, Developer mode, "Load unpacked") and
// dist-extension.zip (what the Chrome Web Store takes; made with Windows' tar, or `zip` on Linux). extension/ itself is left as it is.
// --out <folder> writes the copy somewhere else, with no .zip (the browser tests use this).
// --download also puts the .zip in static/downloads/, so the site's "Get the extension" page offers it for download
// (after the next build of the app).
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'extension');
const args = process.argv.slice(2);
const option = (name) => (args.includes(name) ? args[args.indexOf(name) + 1] : undefined);
const target = option('--out') ? path.resolve(option('--out')) : path.join(root, 'dist-extension');
const zip = option('--out') ? null : path.join(root, 'dist-extension.zip');

const given = option('--site') ?? 'http://localhost:5173';
let site;
try {
	site = new URL(given);
} catch {
	console.error(`Not a web address: ${given}`);
	process.exit(2);
}
if (site.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(site.hostname)) {
	console.error('A public site must use https.');
	process.exit(2);
}

fs.rmSync(target, { recursive: true, force: true });
fs.cpSync(source, target, { recursive: true });

fs.writeFileSync(
	path.join(target, 'config.js'),
	fs.readFileSync(path.join(source, 'config.js'), 'utf8').replace(/self\.DEFAKETIVE_SITE = '[^']*';/, `self.DEFAKETIVE_SITE = '${site.origin}';`)
);
const manifest = JSON.parse(fs.readFileSync(path.join(source, 'manifest.json'), 'utf8'));
const siteScript = manifest.content_scripts.find((entry) => entry.js.includes('site.js'));
siteScript.matches = [`${site.origin}/*`];
// Lets the extension find the DeFaketive tab already open, to reuse it (background.js).
manifest.host_permissions = [`${site.origin}/*`];
fs.writeFileSync(path.join(target, 'manifest.json'), `${JSON.stringify(manifest, null, '\t')}\n`);
console.log(`${path.relative(root, target) || target} reports to ${site.origin} (version ${manifest.version}).`);

if (zip) {
	fs.rmSync(zip, { force: true });
	let made;
	if (process.platform === 'win32') {
		// Windows' own tar writes .zip files with -a (named in full: Git Bash puts a different tar first).
		const tar = path.join(process.env.SystemRoot || 'C:/Windows', 'System32', 'tar.exe');
		made = spawnSync(fs.existsSync(tar) ? tar : 'tar', ['-a', '-c', '-f', zip, '-C', target, ...fs.readdirSync(target)], { stdio: 'inherit' });
	} else {
		// Linux and macOS (the server): `zip` when it is installed, otherwise Python's own zipfile module.
		made = spawnSync('zip', ['-r', '-q', zip, '.'], { cwd: target, stdio: 'inherit' });
		if (made.status !== 0) made = spawnSync('python3', ['-m', 'zipfile', '-c', zip, ...fs.readdirSync(target)], { cwd: target, stdio: 'inherit' });
	}
	if (made.status === 0) console.log('dist-extension.zip is ready for the Chrome Web Store.');
	else console.log('The .zip could not be made; zip the contents of dist-extension/ by hand.');
	if (made.status === 0 && args.includes('--download')) {
		const downloads = path.join(root, 'static', 'downloads');
		fs.mkdirSync(downloads, { recursive: true });
		fs.copyFileSync(zip, path.join(downloads, 'defaketive-extension.zip'));
		console.log('static/downloads/defaketive-extension.zip: build the app again and the "Get the extension" page offers it.');
	}
}
