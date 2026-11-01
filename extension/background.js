// Holds collected reviews for a moment and opens the DeFaketive site to read them.
//
// lazada.js and shopee.js send {type: 'collected', product}. The reviews are kept in this browser's session storage under a
// random id, and the site opens at /check-from-extension?handoff=<id>: in the DeFaketive tab the shopper already
// has open (the one used last), or in a new tab beside the Lazada page when there is none. Finding that tab is
// what the extension's one site permission (host_permissions, the DeFaketive site only) is for. There, site.js asks for them by that id
// ('take-handoff') on the page's behalf, and says 'handoff-used' once the site has them. Only a Lazada or Shopee product
// page may hand reviews over, and only the DeFaketive site may take them. Nothing is sent anywhere by this file.
importScripts('config.js');

const SITE = new URL(self.DEFAKETIVE_SITE);
const MARKETPLACES = ['https://www.lazada.com.ph', 'https://shopee.ph'];
const KEEP_MS = 60 * 60 * 1000;
const ID = /^[0-9a-f-]{36}$/;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
	handle(message, sender).then(sendResponse, () => sendResponse({ ok: false }));
	return true;
});

async function handle(message, sender) {
	const from = sender.url ? new URL(sender.url) : null;
	if (message?.type === 'collected' && MARKETPLACES.includes(from?.origin) && sender.tab) {
		await forgetOld();
		const id = crypto.randomUUID();
		await chrome.storage.session.set({ [`handoff:${id}`]: { product: message.product, at: Date.now() } });
		const reused = await showSite(new URL(`/check-from-extension?handoff=${id}`, SITE).href, sender.tab);
		return { ok: true, reused };
	}
	if (message?.type === 'open-site' && sender.url?.startsWith(chrome.runtime.getURL('popup.html'))) {
		await showSite(new URL('/', SITE).href, null);
		return { ok: true };
	}
	if (from?.origin === SITE.origin && typeof message?.id === 'string' && ID.test(message.id)) {
		const key = `handoff:${message.id}`;
		if (message.type === 'take-handoff') {
			const found = await chrome.storage.session.get(key);
			return { ok: true, product: found[key]?.product ?? null };
		}
		if (message.type === 'handoff-used') {
			await chrome.storage.session.remove(key);
			return { ok: true };
		}
	}
	return { ok: false };
}

/** Open the site at `url` in the DeFaketive tab used last, or in a new tab beside `from` (the Lazada tab, if any). True if a tab was reused. */
async function showSite(url, from) {
	const open = await chrome.tabs.query({ url: `${SITE.origin}/*` });
	const tab = open.sort((a, b) => (b.lastAccessed ?? 0) - (a.lastAccessed ?? 0))[0];
	if (tab?.id !== undefined) {
		await chrome.tabs.update(tab.id, { url, active: true });
		await chrome.windows.update(tab.windowId, { focused: true });
		return true;
	}
	await chrome.tabs.create(from ? { url, index: from.index + 1, openerTabId: from.id } : { url });
	return false;
}

async function forgetOld() {
	const all = await chrome.storage.session.get(null);
	const old = Object.entries(all)
		.filter(([key, value]) => key.startsWith('handoff:') && Date.now() - (value?.at || 0) > KEEP_MS)
		.map(([key]) => key);
	if (old.length) await chrome.storage.session.remove(old);
}
