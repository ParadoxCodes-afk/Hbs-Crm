// Copyright (c) 2026, HBS and contributors
// For license information, please see license.txt

frappe.pages['executive-dashboard'].on_page_load = function(wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Executive Operations & Revenue Intelligence'),
		single_column: true
	});

	wrapper.dashboard = new HbsExecutiveDashboard(page);
	wrapper.dashboard.init();
};

frappe.pages['executive-dashboard'].on_page_show = function(wrapper) {
	if (wrapper.dashboard && wrapper.dashboard.meta && !wrapper.dashboard.isSyncing) {
		wrapper.dashboard.triggerLiveSync('page_show');
	}
};

class HbsExecutiveDashboard {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.meta = null;
		this.selectedExecutive = 'ALL';
		this.activeTab = 'breakdown';
		this.data = null;
		this.isSyncing = false;
		this._updateTimer = null;
	}

	init() {
		this.wrapper.html(`
			<div class="executive-dashboard-container">
				<div class="text-center py-5 text-muted">
					<i class="fa fa-spinner fa-spin fa-2x"></i>
					<p class="mt-2">${__('Loading Executive Dashboard...')}</p>
				</div>
			</div>
		`);

		frappe.call({
			method: 'hbs_crm.hbs_crm.dashboard_api.get_dashboard_meta',
			callback: (r) => {
				if (r.message) {
					this.meta = r.message;
					this.selectedExecutive = this.meta.is_admin ? 'ALL' : this.meta.user;
					this.renderSkeleton();
					this.fetchData();
					this.setupRealtime();
				}
			}
		});
	}

	formatINR(amount) {
		let val = parseFloat(amount || 0);
		if (isNaN(val)) return '₹0';
		if (Math.abs(val) >= 10000000) {
			return '₹' + (val / 10000000).toFixed(2) + 'Cr';
		} else if (Math.abs(val) >= 100000) {
			return '₹' + (val / 100000).toFixed(2) + 'L';
		}
		return '₹' + val.toLocaleString('en-IN', { maximumFractionDigits: 0 });
	}

	formatFullINR(amount) {
		let val = parseFloat(amount || 0);
		return '₹' + val.toLocaleString('en-IN', { maximumFractionDigits: 2 });
	}

	formatTime(val) {
		if (!val || val === '-' || val === 'None' || val === 'null') return '-';
		let s = String(val).trim();
		let m = s.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?/);
		if (m) {
			let h = parseInt(m[1], 10);
			let min = m[2];
			let ampm = h >= 12 ? 'PM' : 'AM';
			let h12 = h % 12 || 12;
			return `${String(h12).padStart(2, '0')}:${min} ${ampm}`;
		}
		return s;
	}

	formatDuration(seconds) {
		const total = Math.max(0, parseInt(seconds || 0, 10));
		if (!total) return '-';
		const h = Math.floor(total / 3600);
		const m = Math.floor((total % 3600) / 60);
		const s = total % 60;
		if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`;
		if (m > 0) return s > 0 ? `${m}m ${s}s` : `${m}m`;
		return `${s}s`;
	}

	formatDate(val) {
		if (!val || val === '-' || val === 'None' || val === 'null') return '-';
		let s = String(val).trim();
		let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
		if (m) {
			return `${m[3]}-${m[2]}-${m[1]}`;
		}
		let m2 = s.match(/^(\d{2})[-/](\d{2})[-/](\d{4})/);
		if (m2) {
			return `${m2[1]}-${m2[2]}-${m2[3]}`;
		}
		try {
			let d = new Date(val);
			if (!isNaN(d.getTime())) {
				let day = String(d.getDate()).padStart(2, '0');
				let month = String(d.getMonth() + 1).padStart(2, '0');
				let year = d.getFullYear();
				return `${day}-${month}-${year}`;
			}
		} catch (e) {}
		return val;
	}

	renderSkeleton() {
		const html = `
			<div class="executive-dashboard-container">
				<!-- Top Header & Filter Bar -->
				<div class="ed-header-bar">
					<div class="ed-title-area">
						<div class="ed-title-row">
							<h2>${__('Executive Operations & Revenue Intelligence')}</h2>
							<div class="ed-live-badge" id="ed-live-status" title="${__('Real-time synchronization active')}">
								<span class="ed-live-dot"></span>
								<span class="ed-live-text">${__('LIVE')}</span>
							</div>
						</div>
						<p>${__('Real-time consolidated tracking across CRM Leads, Tally TSS Renewals, Billing & Receivables')}</p>
					</div>
					<div class="ed-filters-bar">
						<span class="ed-filter-label"><i class="fa fa-calendar"></i> ${__('Date Range:')}</span>
						<input type="date" class="ed-date-input" id="ed-from-date" value="${this.meta.default_from_date}">
						<span style="color:#94a3b8; font-weight:700;">&rarr;</span>
						<input type="date" class="ed-date-input" id="ed-to-date" value="${this.meta.default_to_date}">
						
						<button class="ed-btn" id="ed-btn-apply">
							<i class="fa fa-refresh"></i> ${__('Apply')}
						</button>
						
						<button class="ed-btn ed-btn-outline" id="ed-btn-this-month" title="Current Month">
							${__('This Month')}
						</button>
						<button class="ed-btn ed-btn-outline" id="ed-btn-last-month" title="Last Month">
							${__('Last Month')}
						</button>
						<button class="ed-btn ed-btn-outline" id="ed-btn-fy" title="Current Financial Year">
							${__('Current FY')}
						</button>
						<button class="ed-btn ed-btn-outline" id="ed-btn-all-time" title="All Records">
							${__('All Time')}
						</button>
					</div>
				</div>

				<!-- Executive Selector Carousel -->
				<div class="ed-carousel-section">
					<div class="ed-section-banner">
						<div class="ed-section-meta">
							<h4 class="ed-section-heading"><i class="fa fa-users text-primary"></i> ${__('Team Executives')}</h4>
							<span class="ed-section-desc">${__('Click any executive card below to isolate individual performance, or select "Company Total".')}</span>
						</div>
						<div class="ed-active-exec-badge">
							<i class="fa fa-user-circle text-primary"></i> ${__('Active Scope:')} <strong id="ed-current-exec-label">Company Total</strong>
						</div>
					</div>
					<div class="ed-carousel-wrapper" id="ed-carousel-list">
						<!-- Injected via JS -->
					</div>
				</div>

				<!-- Operational KPI Verticals -->
				<div class="ed-section-banner" style="margin-top: 10px;">
					<div class="ed-section-meta">
						<h4 class="ed-section-heading"><i class="fa fa-th-large text-primary"></i> ${__('Operational Verticals & Metrics')}</h4>
						<span class="ed-section-desc">${__('Consolidated numbers across the 4 core business pillars. Click any box for instant record drill-down.')}</span>
					</div>
					<span class="ed-drill-hint"><i class="fa fa-hand-pointer-o"></i> ${__('Click Any Tile to Drill Down')}</span>
				</div>

				<div class="ed-kpi-grid">
					<!-- 1. LEADS PIPELINE -->
					<div class="ed-kpi-card">
						<div class="ed-kpi-header">
							<div class="ed-kpi-title-block">
								<span class="ed-kpi-title"><i class="fa fa-filter text-primary"></i> ${__('Leads & Pipeline')}</span>
								<span class="ed-kpi-subtitle">${__('New inquiries, follow-ups, won deals & completed visits')}</span>
							</div>
							<span class="ed-kpi-chip chip-blue">${__('CRM PIPELINE')}</span>
						</div>
						<div class="ed-kpi-body">
							<div class="ed-stat-box" data-drill="leads_pending" title="Click to view pending leads">
								<div class="ed-stat-val val-pending" id="kpi-leads-pending">0</div>
								<div class="ed-stat-label">${__('Pending')}</div>
							</div>
							<div class="ed-stat-box" data-drill="leads_overdue" title="Click to view overdue follow-ups">
								<div class="ed-stat-val val-overdue" id="kpi-leads-overdue">0</div>
								<div class="ed-stat-label">${__('Overdue')}</div>
							</div>
							<div class="ed-stat-box" data-drill="leads_generated" title="Click to view newly generated leads">
								<div class="ed-stat-val val-generated" id="kpi-leads-generated">0</div>
								<div class="ed-stat-label">${__('Generated')}</div>
							</div>
							<div class="ed-stat-box" data-drill="leads_won" title="Click to view won deals">
								<div class="ed-stat-val val-won" id="kpi-leads-won">0</div>
								<div class="ed-stat-label">${__('Won Deals')}</div>
							</div>
							<div class="ed-stat-box" data-drill="leads_lost" title="Click to view lost leads">
								<div class="ed-stat-val val-lost" id="kpi-leads-lost">0</div>
								<div class="ed-stat-label">${__('Lost')}</div>
							</div>
						</div>
					</div>

					<!-- 2. TSS RENEWALS -->
					<div class="ed-kpi-card">
						<div class="ed-kpi-header">
							<div class="ed-kpi-title-block">
								<span class="ed-kpi-title"><i class="fa fa-refresh text-warning"></i> ${__('TSS Renewals')}</span>
								<span class="ed-kpi-subtitle">${__('Tally Software Services expiry, sold licenses & lost accounts')}</span>
							</div>
							<span class="ed-kpi-chip chip-amber">${__('SUBSCRIPTION')}</span>
						</div>
						<div class="ed-kpi-body">
							<div class="ed-stat-box" data-drill="tss_pending" title="Click to view pending renewals">
								<div class="ed-stat-val val-pending" id="kpi-tss-pending">0</div>
								<div class="ed-stat-label">${__('Pending')}</div>
							</div>
							<div class="ed-stat-box" data-drill="tss_overdue" title="Click to view overdue renewal follow-ups">
								<div class="ed-stat-val val-overdue" id="kpi-tss-overdue">0</div>
								<div class="ed-stat-label">${__('Overdue')}</div>
							</div>
							<div class="ed-stat-box" data-drill="tss_won" title="Click to view renewed/sold licenses">
								<div class="ed-stat-val val-won" id="kpi-tss-won">0</div>
								<div class="ed-stat-label">${__('Renewed / Sold')}</div>
							</div>
							<div class="ed-stat-box" data-drill="tss_lost" title="Click to view lost renewals">
								<div class="ed-stat-val val-lost" id="kpi-tss-lost">0</div>
								<div class="ed-stat-label">${__('Lost')}</div>
							</div>
						</div>
					</div>

					<!-- 3. BILLING & INCENTIVES -->
					<div class="ed-kpi-card">
						<div class="ed-kpi-header">
							<div class="ed-kpi-title-block">
								<span class="ed-kpi-title"><i class="fa fa-line-chart text-success"></i> ${this.meta.can_view_incentive ? __('Billing & Incentives') : __('Billing & Sales Realization')}</span>
								<span class="ed-kpi-subtitle">${this.meta.can_view_incentive ? __('Sales vouchers, credit adjustments, net realized sales & commissions') : __('Sales vouchers, credit adjustments & net realized sales')}</span>
							</div>
							<span class="ed-kpi-chip chip-emerald">${this.meta.can_view_incentive ? __('REVENUE & COMM') : __('REVENUE')}</span>
						</div>
						<div class="ed-kpi-body">
							<div class="ed-stat-box" data-drill="sales_billing" title="Click to view total sales billing">
								<div class="ed-stat-val val-sales" id="kpi-billing-total">₹0</div>
								<div class="ed-stat-label">${__('Total Billing')}</div>
							</div>
							<div class="ed-stat-box" data-drill="sales_credit" title="Click to view credit notes">
								<div class="ed-stat-val val-credit" id="kpi-billing-credit">₹0</div>
								<div class="ed-stat-label">${__('Credit Note')}</div>
							</div>
							<div class="ed-stat-box" data-drill="sales_net" title="Click to view net sales vouchers">
								<div class="ed-stat-val val-sales" id="kpi-billing-net">₹0</div>
								<div class="ed-stat-label">${__('Net Sales')}</div>
							</div>
							${this.meta.can_view_incentive ? `
							<div class="ed-stat-box" data-drill="sales_incentive" title="Click to view incentive details">
								<div class="ed-stat-val val-won" id="kpi-billing-incentive">₹0</div>
								<div class="ed-stat-label">${__('Incentive Earned')}</div>
							</div>` : ''}
						</div>
					</div>

					<!-- 4. OUTSTANDING RECEIVABLES -->
					<div class="ed-kpi-card">
						<div class="ed-kpi-header">
							<div class="ed-kpi-title-block">
								<span class="ed-kpi-title"><i class="fa fa-money text-danger"></i> ${__('Outstanding Receivables')}</span>
								<span class="ed-kpi-subtitle">${__('Unpaid ledger balances, overdue age buckets & customer counts')}</span>
							</div>
							<span class="ed-kpi-chip chip-rose">${__('COLLECTIONS')}</span>
						</div>
						<div class="ed-kpi-body">
							<div class="ed-stat-box" data-drill="outstanding_all" title="Click to view all outstanding bills">
								<div class="ed-stat-val val-outstanding" id="kpi-out-total">₹0</div>
								<div class="ed-stat-label">${__('Total Due')}</div>
							</div>
							<div class="ed-stat-box" data-drill="outstanding_15" title="Click to view bills overdue >15 days">
								<div class="ed-stat-val" style="color:#f59e0b;" id="kpi-out-15">₹0</div>
								<div class="ed-stat-label">${__('>15 Days Age')}</div>
							</div>
							<div class="ed-stat-box" data-drill="outstanding_30" title="Click to view critical bills overdue >30 days">
								<div class="ed-stat-val val-overdue" id="kpi-out-30">₹0</div>
								<div class="ed-stat-label">${__('>30 Days Age')}</div>
							</div>
							<div class="ed-stat-box" data-drill="outstanding_parties" title="Click to view party-wise balances">
								<div class="ed-stat-val val-pending" id="kpi-out-parties">0</div>
								<div class="ed-stat-label">${__('Parties')}</div>
							</div>
						</div>
					</div>

					<!-- 5. SUPPORT TICKETS -->
					<div class="ed-kpi-card">
						<div class="ed-kpi-header">
							<div class="ed-kpi-title-block">
								<span class="ed-kpi-title"><i class="fa fa-life-ring" style="color:#0d9488;"></i> ${__('Support Tickets')}</span>
								<span class="ed-kpi-subtitle">${__('Ticket intake, resolution throughput, AMC coverage & SLA speed')}</span>
							</div>
							<span class="ed-kpi-chip chip-teal">${__('SUPPORT')}</span>
						</div>
						<div class="ed-kpi-body">
							<div class="ed-stat-box" data-drill="ticket_created" title="Click to view created tickets">
								<div class="ed-stat-val val-new" id="kpi-tk-created">0</div>
								<div class="ed-stat-label">${__('Created')}</div>
							</div>
							<div class="ed-stat-box" data-drill="ticket_pending" title="Click to view open/pending tickets">
								<div class="ed-stat-val val-pending" id="kpi-tk-pending">0</div>
								<div class="ed-stat-label">${__('Pending / Open')}</div>
							</div>
							<div class="ed-stat-box" data-drill="ticket_resolved" title="Click to view resolved tickets">
								<div class="ed-stat-val val-won" id="kpi-tk-resolved">0</div>
								<div class="ed-stat-label">${__('Resolved')}</div>
							</div>
							<div class="ed-stat-box" data-drill="ticket_amc" title="Click to view AMC tickets">
								<div class="ed-stat-val" style="color:#0284c7;" id="kpi-tk-amc">0</div>
								<div class="ed-stat-label">${__('AMC Tickets')}</div>
							</div>
							<div class="ed-stat-box" data-drill="ticket_overdue" title="Click to view overdue ticket follow-ups">
								<div class="ed-stat-val val-overdue" id="kpi-tk-overdue">0</div>
								<div class="ed-stat-label">${__('Overdue')}</div>
							</div>
							<div class="ed-stat-box" data-drill="ticket_resolved" title="Click to view resolved tickets & resolution times">
								<div class="ed-stat-val" style="color:#0d9488;" id="kpi-tk-avg">-</div>
								<div class="ed-stat-label">${__('Avg Resolution')}</div>
							</div>
						</div>
					</div>
				</div>

				<!-- Deep Dive Detail Section -->
				<div class="ed-section-banner" style="margin-top: 10px;">
					<div class="ed-section-meta">
						<h4 class="ed-section-heading"><i class="fa fa-table text-primary"></i> ${__('Analytical Deep-Dive & Breakdowns')}</h4>
						<span class="ed-section-desc">${__('Multi-dimensional audit tables: executive scorecard, item revenue share, and party aging balances.')}</span>
					</div>
				</div>

				<div class="ed-detail-section">
					<div class="ed-tab-nav">
						<button class="ed-tab-btn active" data-tab="breakdown">
							<i class="fa fa-users"></i> ${__('Executive Scorecard')}
						</button>
						<button class="ed-tab-btn" data-tab="products">
							<i class="fa fa-cube"></i> ${__('Product / Item Sales & Incentives')}
						</button>
						<button class="ed-tab-btn" data-tab="parties">
							<i class="fa fa-building"></i> ${__('Party Outstanding Aging')}
						</button>
						${(this.meta && (this.meta.can_view_activity_log || this.meta.is_admin)) ? `
						<button class="ed-tab-btn ed-tab-admin-only" data-tab="activities">
							<i class="fa fa-history"></i> ${__('Daily Activity & Work Log')}
							<span class="ed-tab-badge">${this.meta.is_admin ? __('Admin') : __('Team')}</span>
						</button>
						` : ''}
					</div>

					<div class="ed-table-wrapper" id="ed-tab-content">
						<!-- Table dynamically rendered -->
					</div>
				</div>
			</div>
		`;

		this.wrapper.html(html);
		this.bindEvents();
	}

	bindEvents() {
		const me = this;

		// Filter button
		this.wrapper.find('#ed-btn-apply').on('click', () => {
			this.fetchData();
		});

		// Quick Presets
		const toYMD = (d) => {
			const yr = d.getFullYear();
			const mo = String(d.getMonth() + 1).padStart(2, '0');
			const dy = String(d.getDate()).padStart(2, '0');
			return `${yr}-${mo}-${dy}`;
		};

		// Auto-pick end of month when from-date changes
		this.wrapper.find('#ed-from-date').on('change', function() {
			const val = $(this).val();
			if (val) {
				const parts = val.split('-').map(Number);
				if (parts.length === 3 && parts[0] && parts[1]) {
					me.wrapper.find('#ed-to-date').val(toYMD(new Date(parts[0], parts[1], 0)));
					me.fetchData();
				}
			}
		});

		this.wrapper.find('#ed-btn-this-month').on('click', () => {
			const now = new Date();
			const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
			const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
			this.wrapper.find('#ed-from-date').val(toYMD(firstDay));
			this.wrapper.find('#ed-to-date').val(toYMD(lastDay));
			this.fetchData();
		});

		this.wrapper.find('#ed-btn-last-month').on('click', () => {
			const now = new Date();
			const firstDay = new Date(now.getFullYear(), now.getMonth() - 1, 1);
			const lastDay = new Date(now.getFullYear(), now.getMonth(), 0);
			this.wrapper.find('#ed-from-date').val(toYMD(firstDay));
			this.wrapper.find('#ed-to-date').val(toYMD(lastDay));
			this.fetchData();
		});

		this.wrapper.find('#ed-btn-fy').on('click', () => {
			const now = new Date();
			const startYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
			const fyStart = new Date(startYear, 3, 1);
			const fyEnd = new Date(startYear + 1, 2, 31);
			this.wrapper.find('#ed-from-date').val(toYMD(fyStart));
			this.wrapper.find('#ed-to-date').val(toYMD(fyEnd));
			this.fetchData();
		});

		this.wrapper.find('#ed-btn-all-time').on('click', () => {
			this.wrapper.find('#ed-from-date').val('2020-01-01');
			this.wrapper.find('#ed-to-date').val('2030-12-31');
			this.fetchData();
		});

		// Tab switching
		this.wrapper.find('.ed-tab-btn').on('click', function() {
			me.wrapper.find('.ed-tab-btn').removeClass('active');
			$(this).addClass('active');
			me.activeTab = $(this).data('tab');
			me.renderActiveTab();
		});

		// Drilldown triggers on KPI boxes
		this.wrapper.on('click', '.ed-stat-box', function() {
			const drillType = $(this).data('drill');
			if (drillType) {
				me.openDrilldownModal(drillType);
			}
		});
	}

	fetchData(silent = false) {
		const fromDate = this.wrapper.find('#ed-from-date').val();
		const toDate = this.wrapper.find('#ed-to-date').val();

		if (silent) {
			this.isSyncing = true;
			this.setLiveStatus('syncing');
		}

		frappe.call({
			method: 'hbs_crm.hbs_crm.dashboard_api.get_dashboard_data',
			args: {
				executive: this.selectedExecutive,
				from_date: fromDate,
				to_date: toDate
			},
			freeze: !silent,
			freeze_message: silent ? null : __('Refreshing Dashboard...'),
			callback: (r) => {
				this.isSyncing = false;
				if (r.message) {
					this.data = r.message;
					this.updateUI();
				}
				if (silent) {
					this.setLiveStatus('updated');
					setTimeout(() => {
						this.setLiveStatus('live');
					}, 1800);
				}
			},
			error: () => {
				this.isSyncing = false;
				if (silent) {
					this.setLiveStatus('live');
				}
			}
		});
	}

	setLiveStatus(status) {
		const $badge = this.wrapper.find('#ed-live-status');
		if (!$badge.length) return;

		$badge.removeClass('syncing updated');
		const $text = $badge.find('.ed-live-text');

		if (status === 'syncing') {
			$badge.addClass('syncing');
			$text.html('<i class="fa fa-refresh fa-spin"></i> ' + __('Syncing...'));
		} else if (status === 'updated') {
			$badge.addClass('updated');
			$text.html('<i class="fa fa-check"></i> ' + __('Updated'));
		} else {
			$text.text(__('LIVE'));
		}
	}

	isDashboardVisible() {
		return document.visibilityState === 'visible' &&
			frappe.get_route_str &&
			frappe.get_route_str() === 'executive-dashboard';
	}

	setupRealtime() {
		const doctypes = ['Hbs Crm Lead', 'Hbs Tally Renewal', 'Hbs Incentive Sheet', 'Hbs Outstanding', 'support_ticket'];

		// 1. Subscribe to standard Frappe doctype rooms over Socket.IO
		if (frappe.realtime) {
			doctypes.forEach((dt) => {
				try {
					frappe.realtime.doctype_subscribe(dt);
				} catch (e) {}
			});

			if (this._onRealtimeUpdate) {
				frappe.realtime.off('list_update', this._onRealtimeUpdate);
				frappe.realtime.off('doc_update', this._onRealtimeUpdate);
			}
			this._onRealtimeUpdate = (data) => {
				if (data && doctypes.includes(data.doctype) && this.isDashboardVisible()) {
					this.triggerLiveSync(data.doctype);
				}
			};
			frappe.realtime.on('list_update', this._onRealtimeUpdate);
			frappe.realtime.on('doc_update', this._onRealtimeUpdate);
		}

		// 2. Auto-sync only while Executive Dashboard is actually the active visible route
		$(window).off('focus.ed_dashboard').on('focus.ed_dashboard', () => {
			if (this.meta && !this.isSyncing && this.isDashboardVisible()) {
				this.triggerLiveSync('focus');
			}
		});

		$(document).off('visibilitychange.ed_dashboard').on('visibilitychange.ed_dashboard', () => {
			if (this.meta && !this.isSyncing && this.isDashboardVisible()) {
				this.triggerLiveSync('visibility');
			}
		});

		// 3. Fallback background sync (every 60s) — only when dashboard is visible
		if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
		this.heartbeatInterval = setInterval(() => {
			if (this.meta && !this.isSyncing && this.isDashboardVisible()) {
				this.fetchData(true);
			}
		}, 60000);
	}

	triggerLiveSync(reason) {
		if (this._updateTimer) {
			clearTimeout(this._updateTimer);
		}
		this.setLiveStatus('syncing');
		this._updateTimer = setTimeout(() => {
			this.fetchData(true);
		}, 350);
	}

	updateUI() {
		if (!this.data) return;

		// 1. Update Carousel
		this.renderCarousel();

		// 2. Update KPI Boxes
		const l = this.data.leads || {};
		$('#kpi-leads-pending').text(l.pending || 0);
		$('#kpi-leads-overdue').text(l.overdue || 0);
		$('#kpi-leads-generated').text(l.generated || 0);
		$('#kpi-leads-won').text(l.won || 0);
		$('#kpi-leads-lost').text(l.lost || 0);

		const t = this.data.tss || {};
		$('#kpi-tss-pending').text(t.pending || 0);
		$('#kpi-tss-overdue').text(t.overdue || 0);
		$('#kpi-tss-won').text(t.won || 0);
		$('#kpi-tss-lost').text(t.lost || 0);

		const s = this.data.sales || {};
		$('#kpi-billing-total').text(this.formatINR(s.total_billing));
		$('#kpi-billing-credit').text(this.formatINR(s.credit_note));
		$('#kpi-billing-net').text(this.formatINR(s.net_sales));
		if (this.meta && this.meta.can_view_incentive) {
			$('#kpi-billing-incentive').text(this.formatINR(s.total_incentive));
		}

		const o = this.data.outstanding || {};
		$('#kpi-out-total').text(this.formatINR(o.total_outstanding));
		$('#kpi-out-15').text(this.formatINR(o.above_15_days));
		$('#kpi-out-30').text(this.formatINR(o.above_30_days));
		$('#kpi-out-parties').text(o.parties_count || 0);

		const tk = this.data.tickets || {};
		$('#kpi-tk-created').text(tk.created || 0);
		$('#kpi-tk-pending').text(tk.pending || 0);
		$('#kpi-tk-resolved').text(tk.resolved || 0);
		$('#kpi-tk-amc').text(tk.amc || 0);
		$('#kpi-tk-overdue').text(tk.overdue || 0);
		const avgMins = parseFloat(tk.avg_resolution_mins || 0);
		$('#kpi-tk-avg').text(avgMins > 0 ? this.formatDuration(Math.round(avgMins * 60)) : '-');

		// 3. Render Active Tab Content
		this.renderActiveTab();
	}

	renderCarousel() {
		const listContainer = this.wrapper.find('#ed-carousel-list');
		listContainer.empty();

		const me = this;
		const execs = this.meta.allowed_executives || [];

		// Company Total Card
		if (this.meta.is_admin) {
			const isAllActive = (this.selectedExecutive === 'ALL');
			const totalCard = $(`
				<div class="ed-exec-card ${isAllActive ? 'active' : ''}" data-id="ALL">
					<div class="exec-name"><i class="fa fa-building text-primary"></i> ${__('Company Total')}</div>
					<div class="exec-stat-row">
						<span>${__('All Executives')}</span>
					</div>
					<div class="exec-bottom-row">
						<span class="exec-sales">${this.formatINR(this.data.sales.net_sales)}</span>
						<span class="exec-out">${this.formatINR(this.data.outstanding.total_outstanding)}</span>
					</div>
				</div>
			`);
			totalCard.on('click', function() {
				me.selectedExecutive = 'ALL';
				me.wrapper.find('.ed-exec-card').removeClass('active');
				$(this).addClass('active');
				me.fetchData();
			});
			listContainer.append(totalCard);
		}

		// Individual Executive Cards
		(this.data.carousel || []).forEach(e => {
			const isActive = (me.selectedExecutive === e.id);
			const card = $(`
				<div class="ed-exec-card ${isActive ? 'active' : ''}" data-id="${e.id}">
					<div class="exec-name" title="${e.name}">${e.name}</div>
					<div class="exec-stat-row">
						<span>Leads:</span>
						<span>
							<span class="badge-p">P:${e.leads_p}</span>
							<span class="badge-o">O:${e.leads_o}</span>
							<span class="badge-n">N:${e.leads_n}</span>
						</span>
					</div>
					<div class="exec-stat-row">
						<span>TSS:</span>
						<span>
							<span class="badge-p">P:${e.tss_p}</span>
							<span class="badge-o">O:${e.tss_o}</span>
						</span>
					</div>
					<div class="exec-bottom-row">
						<span class="exec-sales" title="Net Sales">${me.formatINR(e.net_sales)}</span>
						<span class="exec-out" title="Outstanding">${me.formatINR(e.outstanding)}</span>
					</div>
				</div>
			`);

			card.on('click', function() {
				me.selectedExecutive = e.id;
				me.wrapper.find('.ed-exec-card').removeClass('active');
				$(this).addClass('active');
				me.fetchData();
			});
			listContainer.append(card);
		});

		// Update label
		const curExec = execs.find(x => x.id === this.selectedExecutive);
		this.wrapper.find('#ed-current-exec-label').text(curExec ? curExec.name : '');
	}

	renderActiveTab() {
		const container = this.wrapper.find('#ed-tab-content');
		container.empty();

		if (this.activeTab === 'breakdown') {
			this.renderBreakdownTable(container);
		} else if (this.activeTab === 'products') {
			this.renderProductTable(container);
		} else if (this.activeTab === 'parties') {
			this.renderPartyTable(container);
		} else if (this.activeTab === 'activities') {
			this.renderActivityTable(container);
		}
	}

	renderBreakdownTable(container) {
		const rows = this.data.breakdown || [];
		if (!rows.length) {
			container.html(`<div class="p-4 text-center text-muted">${__('No executive records for this period.')}</div>`);
			return;
		}

		let html = `
			<div class="ed-tab-banner">
				<i class="fa fa-info-circle text-primary"></i> <strong>${__('Executive Scorecard:')}</strong> ${__('Cross-functional comparison of active pipeline leads, won/lost deals, completed visits, net sales realized, outstanding ledger balance, and total incentive earned per team executive.')}
			</div>
			<table class="ed-table">
				<thead>
					<tr>
						<th>${__('Executive')}</th>
						<th class="num-cell">${__('Pending')}</th>
						<th class="num-cell">${__('Overdue')}</th>
						<th class="num-cell">${__('Generated')}</th>
						<th class="num-cell">${__('Won')}</th>
						<th class="num-cell">${__('Lost')}</th>
						<th class="num-cell">${__('Net Sales')}</th>
						<th class="num-cell">${__('Outstanding')}</th>
						<th class="num-cell">${__('Incentive')}</th>
					</tr>
				</thead>
				<tbody>
		`;

		rows.forEach(r => {
			html += `
				<tr>
					<td><strong>${r.executive}</strong></td>
					<td class="num-cell val-pending">${r.pending}</td>
					<td class="num-cell val-overdue">${r.overdue}</td>
					<td class="num-cell val-generated">${r.generated}</td>
					<td class="num-cell val-won">${r.won}</td>
					<td class="num-cell val-lost">${r.lost}</td>
					<td class="num-cell val-sales"><strong>${this.formatFullINR(r.net_sales)}</strong></td>
					<td class="num-cell val-outstanding">${this.formatFullINR(r.outstanding)}</td>
					<td class="num-cell" style="color:#0284c7; font-weight:700;">${this.formatFullINR(r.incentive)}</td>
				</tr>
			`;
		});

		html += `</tbody></table>`;
		container.html(html);
	}

	renderProductTable(container) {
		const rows = this.data.product_sales || [];
		if (!rows.length) {
			container.html(`<div class="p-4 text-center text-muted">${__('No product sales data found.')}</div>`);
			return;
		}

		const canIncentive = Boolean(this.meta && this.meta.can_view_incentive);
		const bannerDesc = canIncentive
			? __('Performance metrics showing gross sales quantity, gross sales turnover, credit note adjustments, net realized billing, and total incentive accrued by product category.')
			: __('Performance metrics showing gross sales quantity, gross sales turnover, credit note adjustments, and net realized billing by product category.');

		let html = `
			<div class="ed-tab-banner">
				<i class="fa fa-info-circle text-primary"></i> <strong>${__('Product & Item Revenue Analysis:')}</strong> ${bannerDesc}
			</div>
			<table class="ed-table">
				<thead>
					<tr>
						<th>${__('Item Group / Product')}</th>
						<th class="num-cell">${__('Gross Qty')}</th>
						<th class="num-cell">${__('Gross Sales')}</th>
						<th class="num-cell">${__('Txns')}</th>
						<th class="num-cell">${__('Credit Note')}</th>
						<th class="num-cell">${__('Net Sales')}</th>
						${canIncentive ? `<th class="num-cell">${__('Total Incentive')}</th>` : ''}
					</tr>
				</thead>
				<tbody>
		`;

		rows.forEach(r => {
			html += `
				<tr>
					<td><strong>${r.item_group}</strong></td>
					<td class="num-cell">${r.gross_qty}</td>
					<td class="num-cell">${this.formatFullINR(r.gross_sales_value)}</td>
					<td class="num-cell">${r.gross_txns}</td>
					<td class="num-cell val-credit">${this.formatFullINR(r.credit_note_value)}</td>
					<td class="num-cell val-sales"><strong>${this.formatFullINR(r.net_sales)}</strong></td>
					${canIncentive ? `<td class="num-cell" style="color:#0284c7; font-weight:700;">${this.formatFullINR(r.total_incentive)}</td>` : ''}
				</tr>
			`;
		});

		html += `</tbody></table>`;
		container.html(html);
	}

	renderPartyTable(container) {
		const allRows = this.data.party_outstanding || [];
		const rows = allRows.filter(r => !r.crm_status || String(r.crm_status).trim().toLowerCase() === 'pending');
		if (!rows.length) {
			container.html(`<div class="p-4 text-center text-muted">${__('No pending party outstanding records found.')}</div>`);
			return;
		}

		let html = `
			<div class="ed-tab-banner">
				<i class="fa fa-info-circle text-primary"></i> <strong>${__('Party Outstanding Aging:')}</strong> ${__('Unpaid customer ledger balances categorized into aging buckets: Current (<15 days), Overdue (15–30 days), and Critical (>30 days overdue). Only pending status accounts are displayed.')}
			</div>
			<table class="ed-table">
				<thead>
					<tr>
						<th>${__('Party Name')}</th>
						<th>${__('Contact')}</th>
						<th>${__('Executive')}</th>
						<th>${__('Status')}</th>
						<th class="num-cell">${__('Balance')}</th>
						<th class="num-cell">${__('Current (<15d)')}</th>
						<th class="num-cell">${__('15 - 30 Days')}</th>
						<th class="num-cell">${__('>30 Days')}</th>
						<th>${__('Next Follow-up')}</th>
					</tr>
				</thead>
				<tbody>
		`;

		rows.forEach(r => {
			html += `
				<tr>
					<td><strong>${r.party_name || '-'}</strong></td>
					<td>${r.contact_person || r.contact_number || '-'}</td>
					<td>${frappe.utils.escape_html(r.executive_name || r.executive_1 || '-')}</td>
					<td><span class="badge badge-warning" style="background:#fef3c7; color:#92400e; font-weight:600;">${r.crm_status || 'Pending'}</span></td>
					<td class="num-cell val-outstanding"><strong>${this.formatFullINR(r.balance)}</strong></td>
					<td class="num-cell">${this.formatFullINR(r.current_bucket)}</td>
					<td class="num-cell" style="color:#d97706;">${this.formatFullINR(r.bucket_15_30)}</td>
					<td class="num-cell val-overdue"><strong>${this.formatFullINR(r.bucket_above_30)}</strong></td>
					<td>${this.formatDate(r.followup_date)}</td>
				</tr>
			`;
		});

		html += `</tbody></table>`;
		container.html(html);
	}

	renderActivityTable(container) {
		const me = this;
		if (!this.activityState) {
			this.activityState = {
				date: frappe.datetime.get_today(),
				loading: false,
				data: null
			};
		}

		if (this.activityState.loading) {
			container.html(`
				<div class="p-5 text-center text-muted">
					<i class="fa fa-spinner fa-spin fa-2x"></i>
					<p class="mt-2">${__('Loading executive daily activity log...')}</p>
				</div>
			`);
			return;
		}

		if (!this.activityState.data) {
			this.activityState.loading = true;
			container.html(`
				<div class="p-5 text-center text-muted">
					<i class="fa fa-spinner fa-spin fa-2x"></i>
					<p class="mt-2">${__('Loading executive daily activity log...')}</p>
				</div>
			`);
			frappe.call({
				method: 'hbs_crm.hbs_crm.dashboard_api.get_executive_daily_activities',
				args: {
					date: this.activityState.date
				},
				callback: (r) => {
					me.activityState.loading = false;
					if (r.message) {
						me.activityState.data = r.message;
						me.renderActivityTable(container);
					}
				},
				error: (err) => {
					me.activityState.loading = false;
					container.html(`
						<div class="p-4 text-center text-danger">
							<i class="fa fa-exclamation-triangle fa-2x mb-2"></i>
							<p>${__('Failed to load activity logs or unauthorized access.')}</p>
						</div>
					`);
				}
			});
			return;
		}

		const res = this.activityState.data;
		const kpi = res.kpis || {};
		const hourly = res.hourly || [];
		const scorecard = res.scorecard || [];

		// Find max hourly count for relative team chart height
		let maxHourly = 1;
		hourly.forEach(h => { if (h.count > maxHourly) maxHourly = h.count; });

		let html = `
			<div class="ed-tab-banner">
				<i class="fa fa-shield text-primary"></i> <strong>${__('Daily Activity & Work Log:')}</strong> ${__('Real-time audit trail of remarks, follow-up moves, status transitions, and client visits across CRM Leads, Renewals, and Outstanding.')}
			</div>

			<!-- Activity Filter Toolbar -->
			<div class="ed-act-toolbar" style="margin-bottom: 16px;">
				<div class="ed-act-filter-group">
					<label><i class="fa fa-calendar"></i> ${__('Date')}:</label>
					<input type="date" id="ed-act-date-picker" class="ed-date-input" value="${this.activityState.date}">
					<button class="ed-btn ed-btn-outline ed-btn-xs" id="ed-act-btn-today">${__('Today')}</button>
					<button class="ed-btn ed-btn-outline ed-btn-xs" id="ed-act-btn-yesterday">${__('Yesterday')}</button>
				</div>
				<div class="ed-act-filter-actions">
					<button class="ed-btn ed-btn-outline" id="ed-act-btn-refresh" title="${__('Refresh Live Data')}">
						<i class="fa fa-refresh"></i> ${__('Refresh')}
					</button>
				</div>
			</div>

			<!-- Daily Performance KPI Cards -->
			<div class="ed-act-kpi-row">
				<div class="ed-act-kpi-card kpi-blue">
					<div class="kpi-icon"><i class="fa fa-bolt"></i></div>
					<div class="kpi-body">
						<div class="kpi-val">${kpi.total_activities || 0}</div>
						<div class="kpi-lbl">${__('Total Actions Logged')}</div>
					</div>
				</div>
				<div class="ed-act-kpi-card kpi-sky">
					<div class="kpi-icon"><i class="fa fa-comments-o"></i></div>
					<div class="kpi-body">
						<div class="kpi-val">${kpi.followups_done || 0}</div>
						<div class="kpi-lbl">${__('Follow-ups Submitted')}</div>
					</div>
				</div>
				<div class="ed-act-kpi-card kpi-purple">
					<div class="kpi-icon"><i class="fa fa-building-o"></i></div>
					<div class="kpi-body">
						<div class="kpi-val">${kpi.records_touched || 0}</div>
						<div class="kpi-lbl">${__('Accounts Worked')}</div>
					</div>
				</div>
				<div class="ed-act-kpi-card kpi-green">
					<div class="kpi-icon"><i class="fa fa-trophy"></i></div>
					<div class="kpi-body">
						<div class="kpi-val">${kpi.deals_won || 0}</div>
						<div class="kpi-lbl">${__('Deals Closed / Won')}</div>
					</div>
				</div>
				<div class="ed-act-kpi-card kpi-amber">
					<div class="kpi-icon"><i class="fa fa-calendar-check-o"></i></div>
					<div class="kpi-body">
						<div class="kpi-val">${kpi.rescheduled_count || 0}</div>
						<div class="kpi-lbl">${__('Follow-ups Rescheduled')}</div>
					</div>
				</div>
			</div>

			<!-- Active Working Hours Timeline (Team Overview) -->
			<div class="ed-hourly-card">
				<div class="ed-hourly-header">
					<span class="ed-hourly-title">
						<i class="fa fa-clock-o text-primary"></i> ${__('Team Active Working Hours Timeline')} <small class="text-muted">(9:00 AM – 7:00 PM)</small>
					</span>
					<span class="ed-hourly-sub">
						${__('Live team-wide distribution of call remarks and updates logged throughout the working day')}
					</span>
				</div>
				<div class="ed-hourly-chart">
					${hourly.map(h => {
						const pct = h.count > 0 ? Math.max(12, Math.round((h.count / maxHourly) * 100)) : 0;
						return `
							<div class="ed-hourly-col" title="${h.count} ${__('team activities at')} ${h.label}">
								<div class="ed-hourly-count ${h.count > 0 ? 'has-count' : ''}">${h.count > 0 ? h.count : ''}</div>
								<div class="ed-hourly-bar-track">
									<div class="ed-hourly-bar-fill" style="height: ${pct}%;"></div>
								</div>
								<div class="ed-hourly-label">${h.label}</div>
							</div>
						`;
					}).join('')}
				</div>
			</div>

			<!-- Team Executive Daily Scorecard -->
			<div class="ed-act-scorecard-card">
				<div class="ed-act-scorecard-header">
					<span class="ed-act-scorecard-title">
						<i class="fa fa-user-circle text-primary"></i> ${__('Team Executive Daily Scorecard')} 
						<small class="text-muted ml-2">(${scorecard.filter(x => !x.is_inactive).length} ${__('Active')}, ${scorecard.filter(x => x.is_inactive).length} ${__('Inactive')})</small>
					</span>
					<span class="text-muted" style="font-size:11.5px;">
						<i class="fa fa-hand-pointer-o text-primary"></i> ${__('Click any executive to inspect their individual activity stream & work hours')}
					</span>
				</div>
				<div style="overflow-x:auto;">
					<table class="ed-act-scorecard-table">
						<thead>
							<tr>
								<th>${__('Executive')}</th>
								<th class="text-center" style="width:120px;">${__('Daily Status')}</th>
								<th class="text-right" style="width:95px;">${__('App Time')}</th>
								<th class="text-right" style="width:85px;">${__('Actions')}</th>
								<th class="text-right" style="width:85px;">${__('New Leads')}</th>
								<th class="text-right" style="width:85px;">${__('Follow-ups')}</th>
								<th class="text-right" style="width:75px;">${__('Won')}</th>
								<th class="text-right" style="width:85px;">${__('Visits')}</th>
								<th class="text-center" style="width:120px;">${__('First Action')}</th>
								<th class="text-center" style="width:120px;">${__('Last Action')}</th>
								<th class="text-center" style="width:130px;">${__('Activity Sheet')}</th>
							</tr>
						</thead>
						<tbody>
							${scorecard.length === 0 ? `
								<tr><td colspan="11" class="text-center py-4 text-muted">${__('No executive records found for this date.')}</td></tr>
							` : scorecard.map(s => `
								<tr class="ed-scorecard-row-clickable" data-user="${frappe.utils.escape_html(s.user)}" data-name="${frappe.utils.escape_html(s.user_name || s.user)}">
									<td>
										<strong>${frappe.utils.escape_html(s.user_name || s.user)}</strong>
										${s.user && s.user !== s.user_name ? `<br><small class="text-muted">${frappe.utils.escape_html(s.user)}</small>` : ''}
									</td>
									<td class="text-center">
										${s.is_inactive || s.total_actions === 0 ? `
											<span class="ed-badge-inactive"><i class="fa fa-times-circle"></i> ${__('No Activity')}</span>
										` : `
											<span class="ed-badge-active"><i class="fa fa-check-circle"></i> ${__('Active')}</span>
										`}
									</td>
									<td class="text-right ${s.app_time_seconds > 0 ? 'text-primary font-weight-bold' : 'text-muted'}" style="font-family:'JetBrains Mono', monospace;">${me.formatDuration(s.app_time_seconds)}</td>
									<td class="text-right" style="font-weight:700;">${s.total_actions}</td>
									<td class="text-right ${s.new_leads > 0 ? 'text-success font-weight-bold' : 'text-muted'}">${s.new_leads || 0}</td>
									<td class="text-right">${s.followups}</td>
									<td class="text-right ${s.deals_won > 0 ? 'text-success font-weight-bold' : 'text-muted'}">${s.deals_won}</td>
									<td class="text-right ${s.visits_done > 0 ? 'text-info font-weight-bold' : 'text-muted'}">${s.visits_done}</td>
									<td class="text-center text-muted font-weight-bold">${me.formatTime(s.first_time)}</td>
									<td class="text-center text-muted font-weight-bold">${me.formatTime(s.last_time)}</td>
									<td class="text-center">
										<button class="ed-btn ed-btn-outline ed-btn-xs ed-btn-view-sheet" data-user="${frappe.utils.escape_html(s.user)}" data-name="${frappe.utils.escape_html(s.user_name || s.user)}">
											<i class="fa fa-eye"></i> ${__('View Log')}
										</button>
									</td>
								</tr>
							`).join('')}
						</tbody>
					</table>
				</div>
			</div>
		`;

		container.html(html);

		// Toolbar Bindings
		container.find('#ed-act-date-picker').on('change', function() {
			me.activityState.date = $(this).val();
			me.activityState.data = null;
			me.renderActivityTable(container);
		});

		container.find('#ed-act-btn-today').on('click', () => {
			me.activityState.date = frappe.datetime.get_today();
			me.activityState.data = null;
			me.renderActivityTable(container);
		});

		container.find('#ed-act-btn-yesterday').on('click', () => {
			const d = new Date();
			d.setDate(d.getDate() - 1);
			const yr = d.getFullYear();
			const mo = String(d.getMonth() + 1).padStart(2, '0');
			const dy = String(d.getDate()).padStart(2, '0');
			me.activityState.date = `${yr}-${mo}-${dy}`;
			me.activityState.data = null;
			me.renderActivityTable(container);
		});

		container.find('#ed-act-btn-refresh').on('click', () => {
			me.activityState.data = null;
			me.renderActivityTable(container);
		});

		// Open Executive Day Sheet on row or button click
		container.find('.ed-scorecard-row-clickable').on('click', function(e) {
			const user = $(this).attr('data-user');
			const name = $(this).attr('data-name');
			me.openExecutiveDaySheet(user, name, me.activityState.date);
		});
	}

	openExecutiveDaySheet(user, userName, date) {
		const me = this;
		const initials = (userName || user || 'EX').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

		const modalHtml = $(`
			<div class="ed-daysheet-backdrop">
				<div class="ed-daysheet-modal">
					<div class="ed-daysheet-header">
						<div class="ed-daysheet-profile">
							<div class="ed-daysheet-avatar">${initials}</div>
							<div class="ed-daysheet-user-info">
								<h3>${frappe.utils.escape_html(userName || user)}</h3>
								<p><i class="fa fa-envelope-o"></i> ${frappe.utils.escape_html(user)} &bull; <i class="fa fa-calendar"></i> ${me.formatDate(date)}</p>
							</div>
						</div>
						<div class="ed-daysheet-header-stats">
							<span class="ed-modal-stat-chip"><i class="fa fa-list"></i> <b id="ed-sheet-total-acts">0</b> Actions</span>
							<span class="ed-modal-stat-chip ed-chip-highlight" id="ed-sheet-hours-chip"><i class="fa fa-clock-o"></i> Hours: -</span>
							<button class="ed-modal-close" id="ed-sheet-btn-close" title="Close (Esc)">&times;</button>
						</div>
					</div>

					<div class="ed-daysheet-body" id="ed-sheet-body">
						<div class="p-5 text-center text-muted">
							<i class="fa fa-spinner fa-spin fa-2x"></i>
							<p class="mt-2">${__('Loading executive day activity sheet...')}</p>
						</div>
					</div>
				</div>
			</div>
		`);

		$('body').append(modalHtml);

		const closeModal = () => {
			$(document).off('keydown.ed_daysheet');
			modalHtml.fadeOut(150, () => modalHtml.remove());
		};

		modalHtml.find('#ed-sheet-btn-close').on('click', closeModal);
		modalHtml.on('click', (e) => {
			if ($(e.target).hasClass('ed-daysheet-backdrop')) closeModal();
		});
		$(document).on('keydown.ed_daysheet', (e) => {
			if (e.key === 'Escape' || e.keyCode === 27) closeModal();
		});

		// Fetch detailed data for this specific executive on this date
		frappe.call({
			method: 'hbs_crm.hbs_crm.dashboard_api.get_executive_daily_activities',
			args: {
				date: date,
				executive: user,
				limit: 500
			},
			callback: (r) => {
				if (!r.message) {
					modalHtml.find('#ed-sheet-body').html(`
						<div class="p-5 text-center text-muted">${__('No activity records found.')}</div>
					`);
					return;
				}

				const sheetData = r.message;
				const allRows = sheetData.timeline || [];
				const hourly = sheetData.hourly || [];
				const kpi = sheetData.kpis || {};
				const pageVisits = sheetData.page_visits || [];
				const totalAppSecs = pageVisits.reduce((acc, p) => acc + parseInt(p.active_seconds || 0, 10), 0);
				const maxPageSecs = pageVisits.reduce((mx, p) => Math.max(mx, parseInt(p.active_seconds || 0, 10)), 1);

				modalHtml.find('#ed-sheet-total-acts').text(allRows.length);
				modalHtml.find('#ed-sheet-hours-chip').before(`
					<span class="ed-modal-stat-chip ed-chip-app-time"><i class="fa fa-laptop text-primary"></i> App Time: <b>${me.formatDuration(totalAppSecs)}</b></span>
				`);
				
				// Calculate new leads count
				const newLeadsCount = allRows.filter(x => x.activity_type === 'New Lead Created').length;
				if (newLeadsCount > 0) {
					modalHtml.find('#ed-sheet-hours-chip').before(`
						<span class="ed-modal-stat-chip ed-chip-new-lead"><i class="fa fa-bolt text-success"></i> <b>${newLeadsCount}</b> ${newLeadsCount === 1 ? 'New Lead' : 'New Leads'}</span>
					`);
				}

				// Calculate first & last times
				if (allRows.length > 0) {
					const times = allRows.map(x => x.activity_time).filter(Boolean).sort();
					const firstTime = times[0];
					const lastTime = times[times.length - 1];
					modalHtml.find('#ed-sheet-hours-chip').html(`<i class="fa fa-clock-o"></i> ${me.formatTime(firstTime)} &rarr; ${me.formatTime(lastTime)}`);
				} else {
					modalHtml.find('#ed-sheet-hours-chip').html(`<i class="fa fa-clock-o"></i> No Activity Logged`);
				}

				// Render Sheet Content with interactive filters
				let sheetState = {
					selectedHour: null,
					module: '',
					activity_type: '',
					search: ''
				};

				// Maximum count for hourly chart height
				let maxHourly = 1;
				hourly.forEach(h => { if (h.count > maxHourly) maxHourly = h.count; });

				const renderSheetContent = () => {
					let filtered = allRows;

					if (sheetState.selectedHour !== null) {
						filtered = filtered.filter(r => {
							if (!r.activity_time) return false;
							return parseInt(String(r.activity_time).split(':')[0], 10) === sheetState.selectedHour;
						});
					}

					if (sheetState.module) {
						filtered = filtered.filter(r => r.reference_doctype === sheetState.module);
					}

					if (sheetState.activity_type) {
						filtered = filtered.filter(r => r.activity_type === sheetState.activity_type);
					}

					if (sheetState.search) {
						const q = sheetState.search.toLowerCase().trim();
						filtered = filtered.filter(r => {
							const hay = [
								r.party_name, r.contact_person, r.contact_phone,
								r.reference_name, r.activity_type, r.details,
								r.status_before, r.status_after
							].filter(Boolean).join(' ').toLowerCase();
							return hay.includes(q);
						});
					}

					let selectedHourLabel = '';
					if (sheetState.selectedHour !== null) {
						const matchH = hourly.find(x => x.hour === sheetState.selectedHour);
						selectedHourLabel = matchH ? matchH.label : `${sheetState.selectedHour}:00`;
					}

					const contentHtml = `
						<!-- Executive Specific Active Working Hours Timeline -->
						<div class="ed-hourly-card" style="margin-bottom:0;">
							<div class="ed-hourly-header">
								<span class="ed-hourly-title">
									<i class="fa fa-clock-o text-primary"></i> ${frappe.utils.escape_html(userName || user)}'s Active Working Hours
									<small class="text-muted">(9:00 AM – 7:00 PM)</small>
								</span>
								<span class="ed-hourly-sub">
									${sheetState.selectedHour !== null ? `
										<span style="color:#ea580c; font-weight:700;"><i class="fa fa-filter"></i> Filtered to ${selectedHourLabel}</span>
										<a href="javascript:void(0)" id="ed-sheet-clear-hour" class="ml-2 font-weight-bold text-danger"><i class="fa fa-times"></i> Clear Hour</a>
									` : `
										Click any hour bar to isolate activities
									`}
								</span>
							</div>
							<div class="ed-hourly-chart">
								${hourly.map(h => {
									const pct = h.count > 0 ? Math.max(12, Math.round((h.count / maxHourly) * 100)) : 0;
									const isSel = sheetState.selectedHour === h.hour;
									return `
										<div class="ed-hourly-col ${isSel ? 'selected-hour' : ''}" data-hour="${h.hour}" title="${h.count} actions at ${h.label} - Click to filter">
											<div class="ed-hourly-count ${h.count > 0 ? 'has-count' : ''}">${h.count > 0 ? h.count : ''}</div>
											<div class="ed-hourly-bar-track">
												<div class="ed-hourly-bar-fill" style="height: ${pct}%;"></div>
											</div>
											<div class="ed-hourly-label">${h.label}</div>
										</div>
									`;
								}).join('')}
							</div>
						</div>

						<!-- Pages Visited & Active Screen Time Breakdown -->
						<div class="ed-page-usage-card">
							<div class="ed-hourly-header">
								<span class="ed-hourly-title">
									<i class="fa fa-desktop text-primary"></i> ${__('Pages Visited & Active Screen Time')}
									<small class="text-muted">(${pageVisits.length} ${pageVisits.length === 1 ? 'screen' : 'screens'}, ${me.formatDuration(totalAppSecs)} active)</small>
								</span>
								<span class="ed-hourly-sub">${__('Focused time only (pauses when idle > 2m or tab hidden)')}</span>
							</div>
							${pageVisits.length === 0 ? `
								<div class="text-muted" style="font-size:12px; padding:6px 0;">${__('No page visits tracked for this date yet.')}</div>
							` : `
								<div class="ed-page-usage-list">
									${pageVisits.map(pv => {
										const pct = maxPageSecs > 0 ? Math.max(4, Math.round((parseInt(pv.active_seconds || 0, 10) / maxPageSecs) * 100)) : 0;
										return `
											<div class="ed-page-usage-row">
												<div class="ed-page-usage-name">
													<strong>${frappe.utils.escape_html(pv.page_name || pv.page_route)}</strong>
													<span class="ed-page-visit-pill">${pv.visit_count || 0} ${pv.visit_count === 1 ? 'visit' : 'visits'}</span>
												</div>
												<div class="ed-page-usage-bar-wrap">
													<div class="ed-page-usage-bar" style="width:${pct}%;"></div>
												</div>
												<div class="ed-page-usage-window">${me.formatTime(pv.first_visit_time)} &rarr; ${me.formatTime(pv.last_visit_time)}</div>
												<div class="ed-page-usage-time">${me.formatDuration(pv.active_seconds)}</div>
											</div>
										`;
									}).join('')}
								</div>
							`}
						</div>

						<!-- In-Modal Filter & Search Toolbar -->
						<div class="ed-act-toolbar" style="margin-bottom:0;">
							<div class="ed-act-filter-group">
								<label><i class="fa fa-cubes"></i> Module:</label>
								<select id="ed-sheet-module-filter" class="ed-select-input">
									<option value="">All Modules</option>
									<option value="Hbs Crm Lead" ${sheetState.module === 'Hbs Crm Lead' ? 'selected' : ''}>CRM Leads (${kpi.leads_count || 0})</option>
									<option value="Hbs Tally Renewal" ${sheetState.module === 'Hbs Tally Renewal' ? 'selected' : ''}>TSS Renewals (${kpi.renewals_count || 0})</option>
									<option value="Hbs Outstanding" ${sheetState.module === 'Hbs Outstanding' ? 'selected' : ''}>Outstanding (${kpi.outstanding_count || 0})</option>
									<option value="support_ticket" ${sheetState.module === 'support_ticket' ? 'selected' : ''}>Support Tickets (${kpi.tickets_count || 0})</option>
								</select>
							</div>
							<div class="ed-act-filter-group">
								<label><i class="fa fa-filter"></i> Activity:</label>
								<select id="ed-sheet-type-filter" class="ed-select-input">
									<option value="">All Activities</option>
									<option value="New Lead Created" ${sheetState.activity_type === 'New Lead Created' ? 'selected' : ''}>New Lead Created</option>
									<option value="Ticket Created" ${sheetState.activity_type === 'Ticket Created' ? 'selected' : ''}>Ticket Created</option>
									<option value="Ticket Resolved" ${sheetState.activity_type === 'Ticket Resolved' ? 'selected' : ''}>Ticket Resolved</option>
									<option value="Follow-up Remark" ${sheetState.activity_type === 'Follow-up Remark' ? 'selected' : ''}>Follow-up Remark</option>
									<option value="Payment Remark" ${sheetState.activity_type === 'Payment Remark' ? 'selected' : ''}>Payment Remark</option>
									<option value="Follow-up Rescheduled" ${sheetState.activity_type === 'Follow-up Rescheduled' ? 'selected' : ''}>Follow-up Rescheduled</option>
									<option value="Status Change" ${sheetState.activity_type === 'Status Change' ? 'selected' : ''}>Status Change</option>
									<option value="Deal Won" ${sheetState.activity_type === 'Deal Won' ? 'selected' : ''}>Deal Won</option>
									<option value="Deal Lost" ${sheetState.activity_type === 'Deal Lost' ? 'selected' : ''}>Deal Lost</option>
									<option value="Visit Done" ${sheetState.activity_type === 'Visit Done' ? 'selected' : ''}>Visit Done</option>
								</select>
							</div>
							<div class="ed-act-search-box">
								<i class="fa fa-search"></i>
								<input type="text" id="ed-sheet-search-input" class="ed-act-search-input" placeholder="Search client, phone, remarks..." value="${frappe.utils.escape_html(sheetState.search || '')}">
								${sheetState.search ? `<button id="ed-sheet-search-clear" class="ed-act-search-clear">&times;</button>` : ''}
							</div>
							<div class="ed-act-filter-actions">
								<button class="ed-btn ed-btn-outline" id="ed-sheet-btn-export" title="Export this log as CSV">
									<i class="fa fa-download"></i> Export Log
								</button>
							</div>
						</div>

						<!-- Activity Stream Feed -->
						<div class="ed-daysheet-feed">
							${filtered.length === 0 ? `
								<div class="p-5 text-center text-muted" style="background:#ffffff; border-radius:8px; border:1px solid #e2e8f0;">
									<i class="fa fa-calendar-times-o fa-2x mb-2" style="opacity:0.35;"></i>
									<p><strong>No activities match your filters</strong></p>
									<small>Try clearing hour, module, or search filters.</small>
								</div>
							` : filtered.map(r => {
								let vertPill = 'ed-vert-crm';
								let vertLabel = 'CRM Lead';
								let vertIcon = 'fa-bullseye';
								if (r.reference_doctype === 'Hbs Tally Renewal') {
									vertPill = 'ed-vert-tss';
									vertLabel = 'TSS Renewal';
									vertIcon = 'fa-refresh';
								} else if (r.reference_doctype === 'Hbs Outstanding') {
									vertPill = 'ed-vert-out';
									vertLabel = 'Outstanding';
									vertIcon = 'fa-book';
								} else if (r.reference_doctype === 'support_ticket') {
									vertPill = 'ed-vert-ticket';
									vertLabel = 'Support Ticket';
									vertIcon = 'fa-life-ring';
								}

								let actBadgeCls = 'act-remark';
								let actIcon = 'fa-commenting-o';
								let cardModCls = '';
								let isNewLead = (r.activity_type === 'New Lead Created');
								if (isNewLead) {
									actBadgeCls = 'act-new-lead';
									actIcon = 'fa-star';
									cardModCls = 'card-new-lead';
								} else if (r.activity_type === 'Ticket Created') {
									actBadgeCls = 'act-ticket-new';
									actIcon = 'fa-ticket';
								} else if (r.activity_type === 'Ticket Resolved') {
									actBadgeCls = 'act-won';
									actIcon = 'fa-check-circle';
									cardModCls = 'card-won';
								} else if (r.activity_type === 'Follow-up Rescheduled') {
									actBadgeCls = 'act-reschedule';
									actIcon = 'fa-calendar-check-o';
								} else if (r.activity_type === 'Deal Won') {
									actBadgeCls = 'act-won';
									actIcon = 'fa-trophy';
								} else if (r.activity_type === 'Deal Lost') {
									actBadgeCls = 'act-lost';
									actIcon = 'fa-times-circle';
								} else if (r.activity_type === 'Status Change') {
									actBadgeCls = 'act-status';
									actIcon = 'fa-exchange';
								} else if (r.activity_type === 'Visit Done') {
									actBadgeCls = 'act-visit';
									actIcon = 'fa-map-marker';
								} else if (r.activity_type === 'Payment Remark') {
									actBadgeCls = 'act-payment';
									actIcon = 'fa-money';
								}

								const routeDoc = r.reference_doctype ? frappe.router.slug(r.reference_doctype) : 'hbs-crm-lead';
								const linkUrl = `/app/${routeDoc}/${encodeURIComponent(r.reference_name || '')}`;

								return `
									<div class="ed-feed-card ${cardModCls}">
										<div class="ed-feed-top">
											<div class="ed-feed-meta-left">
												<span class="ed-act-time"><i class="fa fa-clock-o text-muted"></i> ${me.formatTime(r.activity_time)}</span>
												<span class="ed-vert-pill ${vertPill}"><i class="fa ${vertIcon}"></i> ${vertLabel}</span>
												<span class="ed-act-badge ${actBadgeCls}"><i class="fa ${actIcon}"></i> ${frappe.utils.escape_html(r.activity_type)}</span>
											</div>
											${r.follow_up_date ? `
												<span class="ed-fup-date"><i class="fa fa-calendar-check-o text-muted"></i> Next: <b>${me.formatDate(r.follow_up_date)}</b></span>
											` : ''}
										</div>

										<div class="ed-feed-party-row">
											<div class="ed-feed-party-name">
												<a href="${linkUrl}" target="_blank" title="Open record in Desk">
													<i class="fa fa-external-link text-primary mr-1"></i> ${frappe.utils.escape_html(r.party_name || r.reference_name)}
												</a>
												${isNewLead ? `<span class="ed-new-lead-pill"><i class="fa fa-bolt"></i> NEW LEAD</span>` : ''}
											</div>
											<div class="ed-feed-contact-group">
												${(r.status_before && r.status_after) ? `
													<div class="ed-status-trans">
														<span class="st-before">${frappe.utils.escape_html(r.status_before)}</span>
														<i class="fa fa-long-arrow-right"></i>
														<span class="st-after">${frappe.utils.escape_html(r.status_after)}</span>
													</div>
												` : ''}
												${r.contact_person ? `<span><i class="fa fa-user-o text-muted"></i> ${frappe.utils.escape_html(r.contact_person)}</span>` : ''}
												${r.contact_phone ? `<a href="tel:${r.contact_phone.replace(/[^0-9]/g, '')}" class="ed-tel-link"><i class="fa fa-phone"></i> ${frappe.utils.escape_html(r.contact_phone)}</a>` : ''}
											</div>
										</div>

										<div class="ed-feed-remark">
											${frappe.utils.escape_html(r.details || '-')}
										</div>
									</div>
								`;
							}).join('')}
						</div>
					`;

					modalHtml.find('#ed-sheet-body').html(contentHtml);

					// Bind inside modal events
					modalHtml.find('#ed-sheet-module-filter').on('change', function() {
						sheetState.module = $(this).val();
						renderSheetContent();
					});

					modalHtml.find('#ed-sheet-type-filter').on('change', function() {
						sheetState.activity_type = $(this).val();
						renderSheetContent();
					});

					modalHtml.find('#ed-sheet-search-input').on('input', function() {
						sheetState.search = $(this).val();
						renderSheetContent();
						modalHtml.find('#ed-sheet-search-input').focus();
					});

					modalHtml.find('#ed-sheet-search-clear').on('click', () => {
						sheetState.search = '';
						renderSheetContent();
					});

					modalHtml.find('.ed-hourly-col').on('click', function() {
						const hour = parseInt($(this).attr('data-hour'), 10);
						if (sheetState.selectedHour === hour) {
							sheetState.selectedHour = null;
						} else {
							sheetState.selectedHour = hour;
						}
						renderSheetContent();
					});

					modalHtml.find('#ed-sheet-clear-hour').on('click', () => {
						sheetState.selectedHour = null;
						renderSheetContent();
					});

					// Export CSV
					modalHtml.find('#ed-sheet-btn-export').on('click', () => {
						if (!filtered || !filtered.length) {
							frappe.show_alert({ message: __('No activity rows to export'), indicator: 'orange' });
							return;
						}
						let csv = ['Time,Executive,Email,Module,Party / Account,Contact Person,Phone,Action Type,Next Follow-up,Details'];
						filtered.forEach(r => {
							const line = [
								`"${(me.formatTime(r.activity_time) || '').replace(/"/g, '""')}"`,
								`"${(userName || '').replace(/"/g, '""')}"`,
								`"${(user || '').replace(/"/g, '""')}"`,
								`"${(r.reference_doctype || '').replace(/"/g, '""')}"`,
								`"${(r.party_name || r.reference_name || '').replace(/"/g, '""')}"`,
								`"${(r.contact_person || '').replace(/"/g, '""')}"`,
								`"${(r.contact_phone || '').replace(/"/g, '""')}"`,
								`"${(r.activity_type || '').replace(/"/g, '""')}"`,
								`"${(r.follow_up_date || '').replace(/"/g, '""')}"`,
								`"${(r.details || '').replace(/"/g, '""')}"`
							].join(',');
							csv.push(line);
						});
						const blob = new Blob([csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
						const blobUrl = URL.createObjectURL(blob);
						const a = document.createElement('a');
						a.href = blobUrl;
						a.download = `${(userName || user).replace(/\s+/g, '_')}_Activity_Log_${date}.csv`;
						document.body.appendChild(a);
						a.click();
						document.body.removeChild(a);
						URL.revokeObjectURL(blobUrl);
					});
				};

				renderSheetContent();
			}
		});
	}

	openDrilldownModal(metricType) {
		const fromDate = this.wrapper.find('#ed-from-date').val();
		const toDate = this.wrapper.find('#ed-to-date').val();

		frappe.call({
			method: 'hbs_crm.hbs_crm.dashboard_api.get_drilldown_records',
			args: {
				metric_type: metricType,
				executive: this.selectedExecutive,
				from_date: fromDate,
				to_date: toDate
			},
			freeze: true,
			freeze_message: __('Loading Records...'),
			callback: (r) => {
				if (r.message) {
					this.showDrillModalUI(r.message);
				}
			}
		});
	}

	showDrillModalUI(res) {
		const cols = res.columns || [];
		const rows = res.rows || [];
		const doctype = res.doctype || 'Hbs Crm Lead';
		const metricType = res.metric_type || 'records';
		const totalCount = res.total_count ?? rows.length;
		const totalAmount = res.total_amount ?? 0;

		// Clean vertical icons, categories & colors
		const titlesMap = {
			'leads_pending': { title: 'Pending CRM Leads', icon: 'fa fa-clock-o', tag: 'CRM PIPELINE', color: '#f59e0b' },
			'leads_overdue': { title: 'Overdue Lead Follow-ups', icon: 'fa fa-exclamation-triangle', tag: 'CRM PIPELINE', color: '#ef4444' },
			'leads_generated': { title: 'Newly Created Leads', icon: 'fa fa-plus-circle', tag: 'CRM PIPELINE', color: '#3b82f6' },
			'leads_won': { title: 'Won Sales Deals', icon: 'fa fa-check-circle', tag: 'CRM PIPELINE', color: '#10b981' },
			'leads_lost': { title: 'Lost Leads Queue', icon: 'fa fa-times-circle', tag: 'CRM PIPELINE', color: '#64748b' },
			'leads_visits': { title: 'Completed Client Demos & Visits', icon: 'fa fa-map-marker', tag: 'CRM PIPELINE', color: '#8b5cf6' },
			'tss_pending': { title: 'Pending Tally TSS Renewals', icon: 'fa fa-refresh', tag: 'SUBSCRIPTIONS', color: '#f59e0b' },
			'tss_overdue': { title: 'Overdue Renewal Follow-ups', icon: 'fa fa-exclamation-circle', tag: 'SUBSCRIPTIONS', color: '#ef4444' },
			'tss_won': { title: 'Renewed & Sold TSS Licenses', icon: 'fa fa-trophy', tag: 'SUBSCRIPTIONS', color: '#10b981' },
			'tss_lost': { title: 'Lost TSS Subscriptions', icon: 'fa fa-ban', tag: 'SUBSCRIPTIONS', color: '#64748b' },
			'sales_all': { title: 'Sales Billing Transactions', icon: 'fa fa-line-chart', tag: 'REVENUE & COMM', color: '#10b981' },
			'sales_billing': { title: 'Total Sales Billing', icon: 'fa fa-line-chart', tag: 'REVENUE & COMM', color: '#10b981' },
			'sales_credit': { title: 'Credit Notes Issued', icon: 'fa fa-undo', tag: 'REVENUE & COMM', color: '#f97316' },
			'sales_net': { title: 'Net Sales Realized', icon: 'fa fa-check-circle', tag: 'REVENUE & COMM', color: '#10b981' },
			'sales_incentive': { title: 'Incentives Earned', icon: 'fa fa-gift', tag: 'REVENUE & COMM', color: '#059669' },
			'outstanding_all': { title: 'All Pending Receivables', icon: 'fa fa-book', tag: 'COLLECTIONS', color: '#3b82f6' },
			'outstanding_15': { title: 'Receivables Overdue > 15 Days', icon: 'fa fa-clock-o', tag: 'COLLECTIONS', color: '#d97706' },
			'outstanding_30': { title: 'Critical Receivables Overdue > 30 Days', icon: 'fa fa-fire', tag: 'COLLECTIONS', color: '#dc2626' },
			'outstanding_parties': { title: 'Party-Wise Outstanding Balances', icon: 'fa fa-users', tag: 'COLLECTIONS', color: '#6366f1' },
			'ticket_created': { title: 'Support Tickets Created', icon: 'fa fa-plus-circle', tag: 'SUPPORT', color: '#0284c7' },
			'ticket_pending': { title: 'Pending / Open Support Tickets', icon: 'fa fa-clock-o', tag: 'SUPPORT', color: '#f59e0b' },
			'ticket_resolved': { title: 'Resolved Support Tickets', icon: 'fa fa-check-circle', tag: 'SUPPORT', color: '#10b981' },
			'ticket_amc': { title: 'AMC Covered Support Tickets', icon: 'fa fa-shield', tag: 'SUPPORT', color: '#0d9488' },
			'ticket_overdue': { title: 'Overdue Support Ticket Follow-ups', icon: 'fa fa-exclamation-triangle', tag: 'SUPPORT', color: '#ef4444' },
			'ticket_all': { title: 'All Support Tickets', icon: 'fa fa-life-ring', tag: 'SUPPORT', color: '#0d9488' }
		};

		const metaInfo = titlesMap[metricType] || {
			title: __(metricType.replace(/_/g, ' ').toUpperCase()),
			icon: 'fa fa-list',
			tag: 'RECORDS',
			color: '#2563eb'
		};

		// Helper to render interactive table cell
		const renderCell = (k, val, r, idx) => {
			const kLower = String(k).toLowerCase();
			const valStr = val !== null && val !== undefined ? String(val).trim() : '';
			const docId = r.name || r.bill_no;

			// Primary Key (First Column): clickable direct link
			if (idx === 0 && docId && doctype) {
				return `<td><a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(docId)}" target="_blank" class="ed-cell-link" title="Open record"><i class="fa fa-external-link"></i> ${frappe.utils.escape_html(valStr || docId)}</a></td>`;
			}

			if (!valStr || valStr === '-') {
				return `<td class="text-muted text-center">-</td>`;
			}

			// Phone / Mobile: click-to-call
			if (kLower.includes('mobile') || kLower.includes('phone') || kLower.includes('contact_number')) {
				const clean = valStr.replace(/[^0-9]/g, '');
				return `
					<td>
						<div class="ed-contact-cell">
							<a href="tel:${clean}" class="ed-tel-link" title="Call ${valStr}"><i class="fa fa-phone text-primary"></i> ${frappe.utils.escape_html(valStr)}</a>
						</div>
					</td>
				`;
			}

			// Status badge pills
			if (kLower === 'status' || kLower === 'payment_status' || kLower === 'crm_status') {
				const stLower = valStr.toLowerCase();
				let pillCls = 'ed-pill-neutral';
				if (/won|renewed|complete|received|sold/.test(stLower)) pillCls = 'ed-pill-won';
				else if (/pending|open|draft|in progress/.test(stLower)) pillCls = 'ed-pill-pending';
				else if (/lost|cancelled|closed/.test(stLower)) pillCls = 'ed-pill-lost';
				else if (/overdue/.test(stLower)) pillCls = 'ed-pill-overdue';
				return `<td><span class="ed-status-pill ${pillCls}">${frappe.utils.escape_html(valStr)}</span></td>`;
			}

			// Overdue days
			if (kLower.includes('overdue_days') || kLower.includes('overdue days')) {
				const num = Number(val);
				if (!isNaN(num) && num > 0) {
					const badgeCls = num > 30 ? 'ed-overdue-crit' : (num > 15 ? 'ed-overdue-warn' : 'ed-overdue-soft');
					return `<td><span class="ed-overdue-pill ${badgeCls}">${num}d</span></td>`;
				}
				return `<td class="text-muted text-center">-</td>`;
			}

			// Currency / Financial Amounts
			if (
				kLower.includes('amount') ||
				kLower.includes('balance') ||
				kLower.includes('rate') ||
				kLower.includes('incentive') ||
				kLower.includes('deal_value') ||
				kLower.includes('deal value') ||
				kLower.includes('pending amt') ||
				kLower.includes('total balance')
			) {
				const num = Number(val);
				if (!isNaN(num)) {
					if (kLower === 'amount' && r.voucher_type === 'Credit Note') {
						return `<td class="num-cell" style="font-weight:700; color:#dc2626;">-${this.formatFullINR(num)}</td>`;
					}
					return `<td class="num-cell" style="font-weight:700;">${this.formatFullINR(num)}</td>`;
				}
			}

			// Quantity
			if (kLower === 'qty') {
				return `<td class="num-cell">${Number(val) || 0}</td>`;
			}

			// Dates
			if (
				kLower.includes('date') ||
				kLower.includes('expiry') ||
				kLower.includes('created') ||
				kLower.includes('follow') ||
				/^\d{4}-\d{2}-\d{2}/.test(valStr)
			) {
				return `<td>${this.formatDate(valStr)}</td>`;
			}

			// Remarks
			if (kLower.includes('remark')) {
				const esc = frappe.utils.escape_html(valStr);
				return `<td><span class="ed-remark-cell" title="${esc}">${esc}</span></td>`;
			}

			return `<td>${frappe.utils.escape_html(valStr)}</td>`;
		};

		let tableHtml = `
			<table class="ed-table ed-modal-table">
				<thead><tr>
					${cols.map(c => `<th>${c}</th>`).join('')}
				</tr></thead>
				<tbody>
		`;

		if (!rows.length) {
			tableHtml += `<tr><td colspan="${cols.length}" class="text-center py-5 text-muted"><i class="fa fa-info-circle fa-2x mb-2" style="display:block; color:#94a3b8;"></i>${__('No matching records found for this criteria.')}</td></tr>`;
		} else {
			rows.forEach(r => {
				tableHtml += '<tr>';
				Object.entries(r).forEach(([k, val], idx) => {
					tableHtml += renderCell(k, val, r, idx);
				});
				tableHtml += '</tr>';
			});
			tableHtml += `<tr class="ed-no-match-row" style="display:none;"><td colspan="${cols.length}" class="text-center py-4 text-muted"><i class="fa fa-search text-muted mr-1"></i> ${__('No records match your search filter.')}</td></tr>`;
		}
		tableHtml += `</tbody></table>`;

		const totalBadgeHtml = totalAmount > 0 ? `
			<span class="ed-modal-stat-chip ed-chip-highlight" title="Total Value">
				<i class="fa fa-inr"></i> Total: <b>${this.formatFullINR(totalAmount)}</b>
			</span>
		` : '';

		const execBadgeHtml = (this.selectedExecutive && this.selectedExecutive !== 'ALL') ? `
			<span class="ed-modal-stat-chip" title="Executive Scope">
				<i class="fa fa-user"></i> ${frappe.utils.escape_html(this.selectedExecutive)}
			</span>
		` : '';

		const modal = $(`
			<div class="ed-modal-backdrop">
				<div class="ed-modal-content">
					<div class="ed-modal-header">
						<div class="ed-modal-header-left">
							<span class="ed-modal-tag" style="background:${metaInfo.color}15; color:${metaInfo.color}; border:1px solid ${metaInfo.color}30;">
								${metaInfo.tag}
							</span>
							<h3><i class="${metaInfo.icon}" style="color:${metaInfo.color};"></i> ${metaInfo.title}</h3>
						</div>
						<div class="ed-modal-header-right">
							<span class="ed-modal-stat-chip">
								<i class="fa fa-list"></i> <b id="ed-modal-visible-count">${rows.length}</b> / ${totalCount} Records
							</span>
							${totalBadgeHtml}
							${execBadgeHtml}
							<button class="ed-modal-close" title="Close (Esc)">&times;</button>
						</div>
					</div>

					<div class="ed-modal-toolbar">
						<div class="ed-modal-search-wrapper">
							<i class="fa fa-search"></i>
							<input type="text" class="ed-modal-search" placeholder="Type to search in records (Party, Serial, Mobile, Bill, Item, Remark)...">
							<button class="ed-search-clear" style="display:none;" title="Clear search">&times;</button>
						</div>
						<div class="ed-modal-actions">
							<button class="ed-btn ed-modal-open-list" title="Open full list view in Desk">
								<i class="fa fa-external-link"></i> ${__('Open in List')}
							</button>
						</div>
					</div>

					<div class="ed-modal-body">
						${tableHtml}
					</div>

					<div class="ed-modal-footer">
						<span class="text-muted" style="font-size:11px; margin-right:auto;">
							<i class="fa fa-info-circle"></i> ${__('Tip: Click any phone number to dial directly.')}
						</span>
						<button class="ed-btn ed-btn-outline ed-modal-cancel">${__('Close')}</button>
					</div>
				</div>
			</div>
		`);

		$('body').append(modal);

		// Event: Close Handlers
		const closeModal = () => {
			$(document).off('keydown.ed_modal');
			modal.fadeOut(150, () => modal.remove());
		};
		modal.find('.ed-modal-close, .ed-modal-cancel').on('click', closeModal);
		modal.on('click', (e) => {
			if ($(e.target).hasClass('ed-modal-backdrop')) closeModal();
		});
		$(document).on('keydown.ed_modal', (e) => {
			if (e.key === 'Escape' || e.keyCode === 27) closeModal();
		});

		// Event: Open List View
		modal.find('.ed-modal-open-list').on('click', () => {
			closeModal();
			frappe.set_route('List', doctype);
		});

		// Event: Live Search Filter
		const searchInput = modal.find('.ed-modal-search');
		const clearBtn = modal.find('.ed-search-clear');
		searchInput.on('input', function() {
			const q = $(this).val().toLowerCase().trim();
			clearBtn.toggle(!!q);
			let visibleCount = 0;
			modal.find('.ed-modal-table tbody tr:not(.ed-no-match-row)').each(function() {
				const text = $(this).text().toLowerCase();
				if (!q || text.includes(q)) {
					$(this).show();
					visibleCount++;
				} else {
					$(this).hide();
				}
			});
			modal.find('#ed-modal-visible-count').text(visibleCount);
			modal.find('.ed-no-match-row').toggle(visibleCount === 0 && rows.length > 0);
		});
		clearBtn.on('click', () => {
			searchInput.val('').trigger('input').focus();
		});

	}
}
