// The "Check with DeFaketive" button on a Shopee PH product page, and its progress panel.
//
// The same button and panel as lazada.js. Pressing it asks shopee-page.js (inside the page) to collect the reviews,
// shows each step, then hands the reviews with the product's name, price and photo to background.js, which opens the
// report on the DeFaketive site. Shopee changes page without reloading, so the button follows the address: it shows
// on a product page and hides on any other. Everything it draws lives in a shadow root, so Shopee's styles and
// DeFaketive's never mix. It is "open" so accessibility checkers (and the tests) can read it.
(() => {
	if (globalThis.__defaketiveShopeeButtonReady) return;
	globalThis.__defaketiveShopeeButtonReady = true;

	const PRODUCT_PATH = /-i\.\d+\.\d+$|^\/product\/\d+\/\d+$/;
	const IMAGE_HOSTS = ['susercontent.com', 'shopee.ph', 'shopee.com'];
	const SELECTORS = {
		name: ['h1', '[role="heading"][aria-level="1"]'],
		price: ['meta[property="product:price:amount"]', '[aria-label*="price" i]']
	};
	const MESSAGES = {
		check:
			'Shopee wants to make sure you\'re a person. Reload this page, complete Shopee\'s check if one appears, then press Check again.',
		unavailable: "Shopee didn't send this product's reviews. Reload the page and try again in a minute.",
		no_ratings: 'This product has no ratings yet, so there is nothing to check.',
		no_written_reviews: 'This product has ratings but no written reviews, so there is nothing to check.',
		not_a_product: "This doesn't look like a Shopee product page.",
		reload: 'DeFaketive was updated or restarted. Reload this page, then press Check again.'
	};

	const clean = (text, limit) =>
		String(text ?? '')
			.replace(/\s+/g, ' ')
			.trim()
			.slice(0, limit);
	const onProduct = () => PRODUCT_PATH.test(location.pathname);
	const meta = (name) => document.querySelector(`meta[property="${name}"], meta[name="${name}"]`)?.content || '';
	const firstText = (selectors) => {
		for (const selector of selectors) {
			for (const element of document.querySelectorAll(selector)) {
				const text = clean(element.content ?? element.textContent, 2000);
				if (text) return text;
			}
		}
		return '';
	};
	function imageLink() {
		for (const candidate of [meta('og:image'), meta('twitter:image')]) {
			if (!candidate) continue;
			try {
				const link = new URL(candidate, location.href);
				link.protocol = 'https:';
				if (IMAGE_HOSTS.some((host) => link.hostname === host || link.hostname.endsWith(`.${host}`))) return link.href.slice(0, 600);
			} catch {
				/* not a link */
			}
		}
		return '';
	}
	const productDetails = () => ({
		link: `https://shopee.ph${location.pathname}`,
		name: clean((firstText(SELECTORS.name) || meta('og:title') || document.title).replace(/\s*\|\s*Shopee.*$/i, ''), 300),
		price: clean(firstText(SELECTORS.price), 40),
		brand: '',
		seller: '',
		img: imageLink()
	});

	// --- What it draws -------------------------------------------------------------------------------------------
	const host = document.createElement('div');
	host.id = 'defaketive-extension';
	const root = host.attachShadow({ mode: 'open' });
	root.innerHTML = `
		<style>
			:host { all: initial; }
			.box { position: fixed; left: 20px; bottom: 20px; z-index: 2147483646; display: flex; flex-direction: column;
				align-items: flex-start; gap: 8px; font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
				color: #111; }
			button { font: inherit; cursor: pointer; border-radius: 999px; min-height: 40px; padding: 0 16px; }
			button:focus-visible { outline: 3px solid #111; outline-offset: 2px; }
			.check { display: inline-flex; align-items: center; gap: 8px; border: 0; background: #7224c0; color: #fff;
				font-weight: 600; box-shadow: 0 4px 14px rgb(0 0 0 / .25); }
			.check:hover { background: #5f1ea1; }
			.check[disabled] { cursor: progress; opacity: .85; }
			.check svg { width: 18px; height: 18px; }
			.panel { width: min(340px, calc(100vw - 40px)); box-sizing: border-box; background: #fff; border: 1px solid #ddd;
				border-radius: 12px; padding: 14px 16px; box-shadow: 0 8px 28px rgb(0 0 0 / .18); }
			.panel[hidden] { display: none; }
			.title { margin: 0 0 4px; font-weight: 700; }
			.message { margin: 0; color: #333; }
			.bar { height: 6px; margin-top: 10px; background: #eee; border-radius: 999px; overflow: hidden; }
			.bar[hidden] { display: none; }
			.bar span { display: block; height: 100%; width: 0; background: #7224c0; transition: width .3s; }
			.actions { display: flex; gap: 8px; margin-top: 12px; }
			.actions button { min-height: 36px; border: 1px solid #ccc; background: #fff; color: #111; }
			.note { margin: 10px 0 0; font-size: 12px; color: #555; }
			@media (prefers-reduced-motion: reduce) { .bar span { transition: none; } }
		</style>
		<div class="box">
			<div class="panel" role="status" aria-live="polite" hidden>
				<p class="title"></p>
				<p class="message"></p>
				<div class="bar" hidden><span></span></div>
				<div class="actions"><button type="button" class="close">Close</button></div>
				<p class="note">DeFaketive is a student research project, not part of Shopee.</p>
			</div>
			<button type="button" class="check">
				<svg viewBox="0 0 256 256" fill="currentColor" aria-hidden="true">
					<path fill-rule="evenodd" d="M95,57 A58,58 0 0 1 95,173 A58,58 0 0 1 95,57 Z M95,79 A36,36 0 0 1 95,151 A36,36 0 0 1 95,79 Z"/>
					<path d="M118,162 L155,199 L222,132 L198,108 L155,151 L142,138 Z"/>
				</svg>
				<span class="label">Check with DeFaketive</span>
			</button>
		</div>`;
	const $ = (selector) => root.querySelector(selector);
	const button = $('.check');
	const panel = $('.panel');

	function show(title, message, progress = null) {
		panel.hidden = false;
		$('.title').textContent = title;
		$('.message').textContent = message;
		$('.bar').hidden = progress === null;
		if (progress !== null) $('.bar span').style.width = `${Math.round(progress)}%`;
	}
	function finish(label = 'Check again') {
		button.disabled = false;
		$('.label').textContent = label;
	}
	$('.close').addEventListener('click', () => {
		panel.hidden = true;
		button.focus();
	});

	// --- Collecting --------------------------------------------------------------------------------------------
	function stepText(step) {
		if (step.step === 'ratings') return ["Reading this listing's ratings…", 5];
		const done = Number(step.done) || 0;
		return [`Collecting ${step.star}-star reviews… ${step.collected} so far.`, 10 + done * 16];
	}

	async function handOver(result) {
		const product = { ...productDetails(), ratings: result.ratings, levels: result.levels, reviews: result.reviews };
		show('Opening your report…', `${result.reviews.length} reviews collected. Your report opens in DeFaketive.`, 100);
		try {
			const answer = await chrome.runtime.sendMessage({ type: 'collected', product });
			if (!answer?.ok) throw new Error('not handed over');
			show(
				answer.reused ? 'Report opened in your DeFaketive tab' : 'Report opened in a new tab',
				`${result.reviews.length} reviews collected. DeFaketive is reading them now.`,
				100
			);
		} catch {
			show("Couldn't open the report", MESSAGES.reload);
		}
		finish();
	}

	button.addEventListener('click', () => {
		if (button.disabled) return;
		button.disabled = true;
		$('.label').textContent = 'Checking…';
		show('Checking this product', "Reading this listing's ratings…", 2);
		const nonce = crypto.randomUUID();
		const listen = (event) => {
			if (event.source !== window || event.origin !== location.origin) return;
			const data = event.data;
			if (!data || data.source !== 'defaketive-page' || data.nonce !== nonce) return;
			if (data.type === 'step') {
				const [message, progress] = stepText(data.step || {});
				show('Checking this product', message, progress);
				return;
			}
			if (data.type !== 'result') return;
			window.removeEventListener('message', listen);
			const result = data.result || {};
			if (result.status === 'ok' && Array.isArray(result.reviews)) handOver(result);
			else {
				show(result.status === 'check' ? 'Shopee asked for a check' : 'Nothing was checked', MESSAGES[result.status] || MESSAGES.unavailable);
				finish();
			}
		};
		window.addEventListener('message', listen);
		window.postMessage({ source: 'defaketive-extension', type: 'start', nonce }, location.origin);
	});

	// --- Following the page ------------------------------------------------------------------------------------
	let shownFor = '';
	function follow() {
		if (!onProduct()) {
			host.remove();
			shownFor = '';
			return;
		}
		if (shownFor !== location.pathname) {
			// A different product: forget the last one's panel.
			panel.hidden = true;
			if (!button.disabled) finish('Check with DeFaketive');
			shownFor = location.pathname;
		}
		if (!host.isConnected) document.documentElement.append(host);
	}
	follow();
	setInterval(follow, 500);
})();
