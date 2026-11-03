// Where the browser extension can be downloaded from, and whether this site has the file.
//
// The site offers a .zip for download once the server has built one (scripts/build-extension.mjs --download, run by
// deploy/setup-server.sh). Until then, and on a copy of the site that never built it, the team shares the file.
export const EXTENSION_DOWNLOAD = '/downloads/defaketive-extension.zip';
export const EXTENSION_CONTACT = 'mailto:bmacalino_20ur2047@psu.edu.ph?subject=DeFaketive%20extension';

let known: Promise<boolean> | null = null;

/**
 * Whether the .zip is there. Asked once per visit and remembered, so every page that offers the download shares one
 * answer. A missing file comes back as the app's own page (text/html), not as a .zip, so that counts as missing.
 */
export function extensionFileAvailable(): Promise<boolean> {
	known ??= fetch(EXTENSION_DOWNLOAD, { method: 'HEAD', cache: 'no-store' })
		.then((response) => response.ok && !(response.headers.get('content-type') ?? '').includes('text/html'))
		.catch(() => false);
	return known;
}
