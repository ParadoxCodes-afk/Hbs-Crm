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
	if (wrapper.dashboard && wrapper.dashboard.meta) {
		wrapper.dashboard.fetchData(true);
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
							<div class="ed-stat-box" data-drill="leads_visits" title="Click to view completed visits">
								<div class="ed-stat-val" style="color: #0d9488;" id="kpi-leads-visits">0</div>
								<div class="ed-stat-label">${__('Visits')}</div>
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
								<span class="ed-kpi-title"><i class="fa fa-line-chart text-success"></i> ${__('Billing & Incentives')}</span>
								<span class="ed-kpi-subtitle">${__('Sales vouchers, credit adjustments, net realized sales & commissions')}</span>
							</div>
							<span class="ed-kpi-chip chip-emerald">${__('REVENUE & COMM')}</span>
						</div>
						<div class="ed-kpi-body">
							<div class="ed-stat-box" data-drill="sales_all" title="Click to view all sales vouchers">
								<div class="ed-stat-val val-sales" id="kpi-billing-total">₹0</div>
								<div class="ed-stat-label">${__('Total Billing')}</div>
							</div>
							<div class="ed-stat-box" data-drill="sales_credit" title="Click to view credit notes">
								<div class="ed-stat-val val-credit" id="kpi-billing-credit">₹0</div>
								<div class="ed-stat-label">${__('Credit Note')}</div>
							</div>
							<div class="ed-stat-box" data-drill="sales_all" title="Click to view net sales vouchers">
								<div class="ed-stat-val val-sales" id="kpi-billing-net">₹0</div>
								<div class="ed-stat-label">${__('Net Sales')}</div>
							</div>
							<div class="ed-stat-box" data-drill="sales_all" title="Click to view incentive details">
								<div class="ed-stat-val val-won" id="kpi-billing-incentive">₹0</div>
								<div class="ed-stat-label">${__('Incentive Earned')}</div>
							</div>
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

	setupRealtime() {
		const doctypes = ['Hbs Crm Lead', 'Hbs Tally Renewal', 'Hbs Incentive Sheet', 'Hbs Outstanding'];

		// 1. Subscribe to standard Frappe doctype rooms over Socket.IO
		if (frappe.realtime) {
			doctypes.forEach((dt) => {
				try {
					frappe.realtime.doctype_subscribe(dt);
				} catch (e) {}
			});

			frappe.realtime.on('list_update', (data) => {
				if (data && doctypes.includes(data.doctype)) {
					this.triggerLiveSync(data.doctype);
				}
			});

			frappe.realtime.on('doc_update', (data) => {
				if (data && doctypes.includes(data.doctype)) {
					this.triggerLiveSync(data.doctype);
				}
			});
		}

		// 2. Auto-sync on window focus & tab visibility change
		$(window).off('focus.ed_dashboard').on('focus.ed_dashboard', () => {
			if (this.meta && !this.isSyncing) {
				this.triggerLiveSync('focus');
			}
		});

		document.addEventListener('visibilitychange', () => {
			if (document.visibilityState === 'visible' && this.meta && !this.isSyncing) {
				this.triggerLiveSync('visibility');
			}
		});

		// 3. Fallback background sync (every 60s)
		if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
		this.heartbeatInterval = setInterval(() => {
			if (document.visibilityState === 'visible' && this.meta && !this.isSyncing) {
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
		$('#kpi-leads-visits').text(l.completed_visits || 0);

		const t = this.data.tss || {};
		$('#kpi-tss-pending').text(t.pending || 0);
		$('#kpi-tss-overdue').text(t.overdue || 0);
		$('#kpi-tss-won').text(t.won || 0);
		$('#kpi-tss-lost').text(t.lost || 0);

		const s = this.data.sales || {};
		$('#kpi-billing-total').text(this.formatINR(s.total_billing));
		$('#kpi-billing-credit').text(this.formatINR(s.credit_note));
		$('#kpi-billing-net').text(this.formatINR(s.net_sales));
		$('#kpi-billing-incentive').text(this.formatINR(s.total_incentive));

		const o = this.data.outstanding || {};
		$('#kpi-out-total').text(this.formatINR(o.total_outstanding));
		$('#kpi-out-15').text(this.formatINR(o.above_15_days));
		$('#kpi-out-30').text(this.formatINR(o.above_30_days));
		$('#kpi-out-parties').text(o.parties_count || 0);

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
						<th class="num-cell">${__('Visits')}</th>
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
					<td class="num-cell" style="color:#0d9488;">${r.visits}</td>
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

		let html = `
			<div class="ed-tab-banner">
				<i class="fa fa-info-circle text-primary"></i> <strong>${__('Product & Item Revenue Analysis:')}</strong> ${__('Performance metrics showing gross sales quantity, gross sales turnover, credit note adjustments, net realized billing, and total incentive accrued by product category.')}
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
						<th class="num-cell">${__('Total Incentive')}</th>
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
					<td class="num-cell" style="color:#0284c7; font-weight:700;">${this.formatFullINR(r.total_incentive)}</td>
				</tr>
			`;
		});

		html += `</tbody></table>`;
		container.html(html);
	}

	renderPartyTable(container) {
		const rows = this.data.party_outstanding || [];
		if (!rows.length) {
			container.html(`<div class="p-4 text-center text-muted">${__('No party outstanding records found.')}</div>`);
			return;
		}

		let html = `
			<div class="ed-tab-banner">
				<i class="fa fa-info-circle text-primary"></i> <strong>${__('Party Outstanding Aging:')}</strong> ${__('Unpaid customer ledger balances categorized into aging buckets: Current (<15 days), Overdue (15–30 days), and Critical (>30 days overdue).')}
			</div>
			<table class="ed-table">
				<thead>
					<tr>
						<th>${__('Party Name')}</th>
						<th>${__('Contact')}</th>
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
					<td><span class="badge badge-light">${r.crm_status || 'Open'}</span></td>
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

		let tableHtml = `
			<table class="ed-table">
				<thead><tr>
					${cols.map(c => `<th>${c}</th>`).join('')}
				</tr></thead>
				<tbody>
		`;

		if (!rows.length) {
			tableHtml += `<tr><td colspan="${cols.length}" class="text-center py-4 text-muted">${__('No matching records found.')}</td></tr>`;
		} else {
			rows.forEach(r => {
				const docId = r.name || r.bill_no;
				tableHtml += '<tr>';
				Object.entries(r).forEach(([k, val], idx) => {
					if (idx === 0 && docId && doctype) {
						tableHtml += `<td><a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(docId)}" target="_blank" style="font-weight:600; color:#2563eb; text-decoration:none;">${val || docId}</a></td>`;
					} else {
						let displayVal = val !== null && val !== undefined ? val : '-';
						const kLower = String(k).toLowerCase();
						if (
							kLower.includes('date') ||
							kLower.includes('expiry') ||
							kLower.includes('created') ||
							kLower.includes('follow') ||
							(typeof val === 'string' && /^\d{4}-\d{2}-\d{2}/.test(val.trim()))
						) {
							displayVal = this.formatDate(val);
						}
						tableHtml += `<td>${displayVal}</td>`;
					}
				});
				tableHtml += '</tr>';
			});
		}
		tableHtml += `</tbody></table>`;

		const modal = $(`
			<div class="ed-modal-backdrop">
				<div class="ed-modal-content">
					<div class="ed-modal-header">
						<h3><i class="fa fa-list text-primary"></i> ${__(res.metric_type.replace(/_/g, ' ').toUpperCase())} (${rows.length} ${__('Records')})</h3>
						<button class="ed-modal-close">&times;</button>
					</div>
					<div class="ed-modal-body">
						${tableHtml}
					</div>
					<div class="ed-modal-footer">
						<button class="ed-btn ed-btn-outline ed-modal-cancel">${__('Close')}</button>
						<button class="ed-btn ed-modal-open-list"><i class="fa fa-external-link"></i> ${__('Open in List View')}</button>
					</div>
				</div>
			</div>
		`);

		$('body').append(modal);

		modal.find('.ed-modal-close, .ed-modal-cancel').on('click', () => modal.remove());
		modal.on('click', (e) => {
			if ($(e.target).hasClass('ed-modal-backdrop')) modal.remove();
		});
		modal.find('.ed-modal-open-list').on('click', () => {
			modal.remove();
			frappe.set_route('List', doctype);
		});
	}
}
