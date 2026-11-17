// Lightweight Desk Page & Active Screen Time Tracker
// Measures active focused time (pauses on tab hide or >2m user idle) with minimal RAM/CPU overhead.
(function () {
	if (window.__hbs_page_tracker_loaded) return;
	window.__hbs_page_tracker_loaded = true;

	const IDLE_MS = 120000;       // 2 min idle cutoff
	const HEARTBEAT_MS = 120000;  // Flush active time every 2 min
	const CHECK_MS = 60000;       // Single 60s background check
	const ACTIVITY_THROTTLE_MS = 5000;
	const ENDPOINT = "/api/method/hbs_crm.hbs_crm.doctype.hbs_page_visit_log.hbs_page_visit_log.log_page_visit";

	const DOCTYPE_LABELS = {
		"Hbs Crm Lead": "CRM Leads",
		"Hbs Tally Renewal": "Tally Renewals",
		"Hbs Outstanding": "Outstanding Receivables",
		"Hbs Incentive Sheet": "Incentives & Billing",
		"Hbs Customer": "Customers",
		"Hbs Product": "Products",
		"Hbs Lead Team Hierarchy": "Lead Team Hierarchy",
		"Hbs User Hierarchy": "User Hierarchy",
		"Hbs CRM Settings": "CRM Settings",
		"Hbs CRM Email Settings": "CRM Email Settings",
		"Hbs Executive Activity Log": "Executive Activity Logs",
		"support_ticket": "Support Tickets",
		"support_ticket_ledger": "Support Contract Ledgers",
		"support_contract_followup": "Support Contract Follow-ups",
		"support_team_hierarchy": "Support Team Hierarchy",
		"Hbs Support Settings": "Support Settings"
	};

	const PAGE_LABELS = {
		"executive-dashboard": "Executive Dashboard",
		"hbs-crm": "HBS CRM Home",
		"support-ticket": "Support Home"
	};

	function toTitle(str) {
		return String(str || "")
			.replace(/[-_]+/g, " ")
			.replace(/\b\w/g, (c) => c.toUpperCase())
			.trim();
	}

	function resolvePageMeta() {
		if (!window.frappe || !frappe.get_route) return null;
		const r = frappe.get_route() || [];
		const head = String(r[0] || "").trim();
		const second = String(r[1] || "").trim();

		if (!head || head === "home") {
			return { page_name: "Home", page_route: "home" };
		}
		if (head === "Workspaces") {
			const ws = second || "Home";
			return { page_name: `Workspace: ${ws}`, page_route: `Workspaces/${ws}` };
		}
		if (head === "List" || head === "Form" || head === "Tree" || head === "Kanban" || head === "Calendar") {
			const dt = second || head;
			return {
				page_name: DOCTYPE_LABELS[dt] || dt,
				page_route: `${head}/${dt}`
			};
		}
		if (head === "query-report") {
			const rep = second || "Report";
			return { page_name: rep, page_route: `query-report/${rep}` };
		}
		if (head === "Report") {
			const dt = second || "Report";
			return {
				page_name: `Report: ${DOCTYPE_LABELS[dt] || dt}`,
				page_route: `Report/${dt}`
			};
		}
		if (head === "dashboard-view") {
			const db = second || "Dashboard";
			return { page_name: `Dashboard: ${db}`, page_route: `dashboard-view/${db}` };
		}

		const slug = head.toLowerCase();
		return {
			page_name: PAGE_LABELS[slug] || toTitle(head),
			page_route: second ? `${head}/${second}` : head
		};
	}

	let trackerStarted = false;
	function startTracker() {
		if (trackerStarted) return;
		if (!window.frappe || !frappe.session || !frappe.router) return;
		const user = frappe.session.user;
		if (!user || user === "Guest" || user === "Administrator") return;
		trackerStarted = true;

		let currentMeta = null;
		let segmentStartTs = null;
		let lastInteractionTs = Date.now();
		let lastThrottleTs = 0;
		let pendingMs = 0;
		let pendingVisit = 0;

		function commitSegment(now) {
			if (segmentStartTs !== null) {
				const effectiveEnd = Math.min(now, lastInteractionTs + IDLE_MS);
				if (effectiveEnd > segmentStartTs) {
					pendingMs += (effectiveEnd - segmentStartTs);
				}
			}
			const isVisible = document.visibilityState === "visible";
			const isActive = (now - lastInteractionTs) < IDLE_MS;
			segmentStartTs = (isVisible && isActive) ? now : null;
		}

		function sendPayload(meta, secs, isNewVisit, keepalive) {
			if (!meta || (!secs && !isNewVisit)) return;
			const body = new URLSearchParams({
				page_name: meta.page_name,
				page_route: meta.page_route,
				active_seconds: String(secs),
				is_new_visit: String(isNewVisit ? 1 : 0)
			});

			try {
				fetch(ENDPOINT, {
					method: "POST",
					credentials: "same-origin",
					keepalive: !!keepalive,
					headers: {
						"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
						"X-Frappe-CSRF-Token": frappe.csrf_token || ""
					},
					body: body.toString()
				}).catch(() => {});
			} catch (e) {
				// Fail-safe: tracking must never affect UI
			}
		}

		function flush(keepalive) {
			const now = Date.now();
			commitSegment(now);
			const secs = Math.floor(pendingMs / 1000);
			const visit = pendingVisit;
			if (!currentMeta || (!secs && !visit)) return;

			pendingMs -= secs * 1000;
			pendingVisit = 0;
			sendPayload(currentMeta, secs, visit, keepalive);
		}

		function onRouteChange() {
			const nextMeta = resolvePageMeta();
			if (!nextMeta) return;

			if (currentMeta && currentMeta.page_name === nextMeta.page_name) {
				// Stay within same screen category (e.g. List <-> Form): keep timer continuous
				const now = Date.now();
				lastInteractionTs = now;
				if (segmentStartTs === null && document.visibilityState === "visible") {
					segmentStartTs = now;
				}
				return;
			}

			if (currentMeta) {
				flush(false);
			}

			const now = Date.now();
			currentMeta = nextMeta;
			pendingMs = 0;
			pendingVisit = 1;
			lastInteractionTs = now;
			segmentStartTs = document.visibilityState === "visible" ? now : null;
		}

		function onUserActivity() {
			const now = Date.now();
			if (now - lastThrottleTs < ACTIVITY_THROTTLE_MS) return;
			lastThrottleTs = now;
			if (document.visibilityState !== "visible") return;

			if (segmentStartTs === null) {
				segmentStartTs = now;
			}
			lastInteractionTs = now;
		}

		const passiveOpts = { passive: true };
		["mousemove", "keydown", "mousedown", "scroll", "touchstart"].forEach((evt) => {
			window.addEventListener(evt, onUserActivity, passiveOpts);
		});

		document.addEventListener("visibilitychange", () => {
			if (document.visibilityState === "hidden") {
				flush(true);
				segmentStartTs = null;
			} else {
				const now = Date.now();
				lastInteractionTs = now;
				segmentStartTs = now;
			}
		});

		window.addEventListener("pagehide", () => flush(true));

		frappe.router.on("change", onRouteChange);

		setInterval(() => {
			const now = Date.now();
			commitSegment(now);
			if (
				pendingMs >= HEARTBEAT_MS ||
				(pendingVisit && document.visibilityState === "visible") ||
				(segmentStartTs === null && pendingMs >= 1000)
			) {
				flush(false);
			}
		}, CHECK_MS);

		onRouteChange();
	}

	if (window.jQuery) {
		jQuery(document).on("startup", startTracker);
		if (window.frappe && frappe.router && frappe.session && frappe.session.user) {
			startTracker();
		}
	} else {
		window.addEventListener("DOMContentLoaded", startTracker);
	}
})();
