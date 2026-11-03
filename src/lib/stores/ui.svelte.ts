/** Which pop-ups are open. Any page can open the sign-in pop-up through this. */
class Ui {
	authOpen = $state(false);
	authKind = $state<'signin' | 'signup'>('signin');
	/** A line shown above the form, e.g. "You've used your 3 free scans today." */
	authNotice = $state('');
	/** Where to go once the visitor has signed in. */
	afterAuth = $state('');

	/** The Ctrl+K search and jump pop-up. */
	commandOpen = $state(false);
	/** Set when "/" is pressed away from a scan bar: the Analyze page focuses its bar when it opens. */
	focusScan = $state(false);

	/** True while someone is signing out or deleting their account, so the app doesn't ask them to sign back in. */
	leaving = $state(false);

	termsOpen = $state(false);
	termsSection = $state<'terms' | 'privacy'>('terms');

	/** The welcome tour: opens by itself right after an account is created; Settings and Ctrl+K open it again. */
	tourOpen = $state(false);

	/** The "Report a problem" pop-up (problem-report-dialog.svelte), and what it starts on. */
	reportOpen = $state(false);
	reportCategory = $state('other');

	openAuth(kind: 'signin' | 'signup' = 'signin', notice = '', after = '') {
		this.authKind = kind;
		this.authNotice = notice;
		this.afterAuth = after;
		this.authOpen = true;
	}

	openReport(category = 'other') {
		this.reportCategory = category;
		this.reportOpen = true;
	}

	openTerms(section: 'terms' | 'privacy' = 'terms') {
		this.termsSection = section;
		this.termsOpen = true;
	}
}

export const ui = new Ui();
