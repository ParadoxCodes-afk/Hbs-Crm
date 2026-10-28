// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Tally Renewal", {
	refresh(frm) {
		setup_field_permissions(frm);
		setup_all_contacts_grid(frm);
		render_activity_timeline(frm);
		render_old_remarks_timeline(frm);
		render_tickets_tab(frm);
		frm.set_df_property("pi_number", "read_only", 1);
		frm.set_df_property("quotation_date", "hidden", 1);
		if (frm.doc.quotation_date !== frappe.datetime.get_today()) {
			frm.set_value("quotation_date", frappe.datetime.get_today());
		}
		apply_custom_section_styles(frm);
		auto_fill_quote_items_client(frm);

		if (frm.is_new() && !frm.doc.crm_ex_1) {
			frm.set_value("crm_ex_1", frappe.session.user);
		}

		if (!frm.is_new() && (frm.doc.tally_serial || frm.doc.tss_tally_serial)) {
			auto_sync_portal_on_open(frm);
		}

		frm.clear_custom_buttons();

		if (!frm.is_new()) {
			// Prominent View Quotation button on the top toolbar
			frm.add_custom_button(__("📄 View Quotation"), function () {
				open_quotation_preview_dialog(frm, "Hbs Tally Renewal");
			});

			// All users with view permission can log follow-up
			frm.add_custom_button(__("+ Follow-up"), function () {
				open_follow_up_dialog(frm);
			}).addClass("btn-primary");

			// All users with view permission can send TSS quotation email to client
			frm.add_custom_button(__("Send Quotation to Client"), function () {
				open_email_dialog(frm);
			}, __("Actions"));

			// Take Over Renewal button (when current user is not Executive 1 and renewal is Lost or inactive > 15 days)
			if (frm.doc.crm_ex_1 !== frappe.session.user) {
				let is_lost = (
					(frm.doc.crm_status || "").trim().toLowerCase() === "lost" ||
					(frm.doc.crm_stage || "").trim().toLowerCase() === "lost"
				);
				let last_date = frm.doc.last_remarks_date || frm.doc.contact_on || frm.doc.creation;
				let diff = last_date ? frappe.datetime.get_diff(frappe.datetime.get_today(), last_date) : 999;

				if (is_lost || diff > 15) {
					let label = is_lost ? __("⚡ Take Over & Revive") : __("⚡ Take Over Renewal");
					let confirm_msg = is_lost
						? __("Are you sure you want to revive and take over lost Renewal #{0}? You will become Executive 1.", [frm.doc.name])
						: __("Are you sure you want to take over Renewal #{0} (inactive for {1} days)? You will become Executive 1.", [frm.doc.name, diff]);

					frm.add_custom_button(label, function () {
						frappe.confirm(confirm_msg, function () {
							frappe.call({
								method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.take_over_renewal",
								args: { renewal_name: frm.doc.name },
								freeze: true,
								freeze_message: __("Taking over renewal..."),
								callback: function (res) {
									if (res.message) {
										frappe.show_alert({
											message: res.message.message,
											indicator: "green"
										});
										frm.reload_doc();
									}
								}
							});
						});
					}, __("Actions"));
				}
			}

			// Admin and Hierarchy Owner only button
			check_if_owner_or_admin(function (is_owner_admin) {
				if (is_owner_admin) {
					frm.add_custom_button(__("👤 Assign Executive"), function () {
						open_assign_dialog(frm);
					});

					frm.add_custom_button(__("🔄 Sync Portal API"), function () {
						frappe.call({
							method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_portal",
							args: { name: frm.doc.name, only_expiry: 0 },
							freeze: true,
							freeze_message: __("Syncing all fields from Tally Portal API..."),
							callback: function (r) {
								if (r && r.message && r.message.status === "success") {
									frappe.show_alert({
										message: __("Portal details synced ({0} fields updated)", [r.message.synced_count || 0]),
										indicator: "green"
									});
									frm.reload_doc();
								} else if (r && r.message) {
									frappe.msgprint(r.message.message || __("Sync failed"));
								}
							}
						});
					}, __("Actions"));
				}
			});
		}
	},

	license(frm) {
		auto_fill_quote_items_client(frm);
	},

	flavour(frm) {
		auto_fill_quote_items_client(frm);
	},

	portal_expiry_date(frm) {
		apply_custom_section_styles(frm);
	},

	product_ver(frm) {
		format_client_tally_version(frm);
	},

	tally_version(frm) {
		format_client_tally_version(frm);
	},

	additional_discount(frm) {
		calculate_totals(frm);
	},

	tally_serial(frm) {
		check_and_warn_duplicate_serial(frm);
	},

	tss_tally_serial(frm) {
		check_and_warn_duplicate_serial(frm);
	},

	validate(frm) {
		let serial = frm.doc.tss_tally_serial || frm.doc.tally_serial;
		if (serial) {
			let s = String(serial).trim();
			if (!is_genuine_tally_serial(s)) {
				frappe.msgprint({
					title: __("Invalid Serial Number"),
					indicator: "red",
					message: __("Invalid Serial Number")
				});
				frappe.validated = false;
				return;
			}
		}
	}
});

function format_client_tally_version(frm) {
	if (frm.doc.tally_version) return;
	let ver = (frm.doc.product_ver || "").toString().trim();
	if (!ver) return;
	frm.set_value("tally_version", ver);
}

function check_if_owner_or_admin(callback) {
	if (frappe.session.user === "Administrator" || frappe.user.has_role("System Manager")) {
		callback(true);
		return;
	}

	if (window._hbs_is_owner_or_admin !== undefined) {
		callback(window._hbs_is_owner_or_admin);
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_user_hierarchy_role",
		callback: function (r) {
			let is_allowed = !!(r.message && r.message.is_owner_or_admin);
			window._hbs_is_owner_or_admin = is_allowed;
			callback(is_allowed);
		}
	});
}

function setup_field_permissions(frm) {
	// Quote calculation fields are read-only
	["total_before_tax", "total_tax", "total_after_tax", "final_total"].forEach(fn => {
		frm.set_df_property(fn, "read_only", 1);
	});

	// 1. ALWAYS Read-Only (view-only on both creation & alteration):
	// Synced via API / Excel or updated strictly via Follow-up Dialog
	const always_view_only = [
		"mau",
		"qau",
		"crm_priority",
		"rfm_segment",
		"crm_status",
		"crm_stage",
		"follow_up_date",
		"last_remarks_date",
		"contact_on",
		"last_updated",
		"portal_expiry_date",
		"last_updated_api",
		"crm_ref",
		"tss_ranking",
		"tss_last_renewal_mode",
		"previous_tss_expiry_date",
		"last_ping_date",
		"last_tss_renewal_date",
		"usage_type",
		"tepl",
		"old_remarks"
	];

	// Make sure Frappe never auto-hides them by keeping df.read_only = 0
	always_view_only.forEach(fn => {
		if (frm.fields_dict[fn]) {
			frm.set_df_property(fn, "read_only", 0);
			if (frm.fields_dict[fn].$wrapper) {
				frm.fields_dict[fn].$wrapper.show().css("display", "block !important");
				frm.fields_dict[fn].$wrapper.find("input, select, textarea")
					.prop("readonly", true)
					.prop("disabled", true)
					.css({
						"pointer-events": "none",
						"cursor": "default"
					});
			}
		}
	});

	// 2. Creation fields that become READ-ONLY on ALTERATION:
	const lock_on_alteration = [
		"tss_tally_serial",
		"tally_serial",
		"license",
		"tally_version",
		"acc_expiry_date",
		"partner_name",
		"frequency_of_usage",
		"upgrade_priority",
		"migration_priority",
		"tally_parent",
		"multi_site",
		"site_number",
		"product_ver",
		"last_called_on",
		"cc_amount",
		"closure_serial_number",
		"buisness_nature",
		"buisness_activity",
		"customer_serial",
		"ts9_priority",
		"business_segment",
		"mca_registered",
		"tpel",
		"crm_executive",
		"crm_type",
		"crm_departments",
		"product_family",
		"flavour",
		"portal_acc_name",
		"acc_start_date",
		"portal_owner",
		"license_type",
		"release",
		"account_id",
		"admin_id",
		"previous_lcp",
		"ping_in_this_quarter",
		"portal_contact",
		"portal_mobile",
		"portal_phone",
		"portal_partner_name",
		"portal_email",
		"gstin",
		"state",
		"pincode",
		"portal_address",
		"mca_flag",
		"tvu_priority",
		"paid_tvu_end_date",
		"paid_tvu_quantity",
		"director_contact_person",
		"director_type",
		"director_gst",
		"director_nature",
		"director_mobile",
		"director_email",
		"director_state",
		"director_pincode",
		"director_turnover_slab",
		"director_turnover",
		"director_address"
	];

	// 3. Fields that remain EDITABLE during ALTERATION for normal users:
	const editable_on_alteration = [
		"cc_acc_name",
		"cc_contact",
		"cc_mobile",
		"cc_phone",
		"cc_email",
		"cc_email_cc",
		"address",
		"led_city",
		"cc_state",
		"cc_pincode",
		"crm_ex_1"
	];

	check_if_owner_or_admin(function (is_admin) {
		if (frm.is_new()) {
			// During creation: allow user to input initial identity & contact info
			lock_on_alteration.forEach(fn => {
				if (frm.fields_dict[fn]) {
					frm.set_df_property(fn, "read_only", 0);
					if (frm.fields_dict[fn].$wrapper) {
						frm.fields_dict[fn].$wrapper.find("input, select, textarea")
							.prop("readonly", false)
							.prop("disabled", false)
							.css({
								"pointer-events": "auto",
								"cursor": "auto"
							});
					}
				}
			});
			editable_on_alteration.forEach(fn => {
				if (frm.fields_dict[fn]) {
					frm.set_df_property(fn, "read_only", 0);
					if (frm.fields_dict[fn].$wrapper) {
						frm.fields_dict[fn].$wrapper.find("input, select, textarea")
							.prop("readonly", false)
							.prop("disabled", false)
							.css({
								"pointer-events": "auto",
								"cursor": "auto"
							});
					}
				}
			});
		} else {
			// During alteration: lock ALL fields except cc_mobile (unless Admin/Owner)
			lock_on_alteration.forEach(fn => {
				if (frm.fields_dict[fn]) {
					if (!is_admin) {
						frm.set_df_property(fn, "read_only", 0);
						if (frm.fields_dict[fn].$wrapper) {
							frm.fields_dict[fn].$wrapper.show().css("display", "block !important");
							frm.fields_dict[fn].$wrapper.find("input, select, textarea")
								.prop("readonly", true)
								.prop("disabled", true)
								.css({
									"pointer-events": "none",
									"cursor": "default"
								});
						}
					} else {
						frm.set_df_property(fn, "read_only", 0);
						if (frm.fields_dict[fn].$wrapper) {
							frm.fields_dict[fn].$wrapper.find("input, select, textarea")
								.prop("readonly", false)
								.prop("disabled", false)
								.css({
									"pointer-events": "auto",
									"cursor": "auto"
								});
						}
					}
				}
			});

			editable_on_alteration.forEach(fn => {
				if (frm.fields_dict[fn]) {
					frm.set_df_property(fn, "read_only", 0);
					if (frm.fields_dict[fn].$wrapper) {
						frm.fields_dict[fn].$wrapper.find("input, select, textarea")
							.prop("readonly", false)
							.prop("disabled", false)
							.css({
								"pointer-events": "auto",
								"cursor": "auto"
							});
					}
				}
			});

			// Quote tab editing: Allow users to alter items and item_name
			frm.set_df_property("items", "read_only", 0);
			if (frm.fields_dict.items && frm.fields_dict.items.grid) {
				let grid = frm.fields_dict.items.grid;
				grid.cannot_add_rows = false;
				["item_name", "qty", "rate", "tax", "amount", "hsn", "description"].forEach(col => {
					grid.update_docfield_property(col, "read_only", 0);
				});
				grid.update_docfield_property("discount_amount", "read_only", 1);
				if (grid.wrapper) {
					grid.wrapper.find(".grid-remove-rows, .grid-add-row, .grid-delete-row, .grid-duplicate-row").show();
				}
				grid.refresh();
			}

			frm.set_df_property("additional_discount", "read_only", 1);
			if (!is_admin) {
				["payment_terms", "delivery", "support", "taxes", "validity"].forEach(fn => {
					frm.set_df_property(fn, "read_only", 1);
				});
			} else {
				["payment_terms", "delivery", "support", "taxes", "validity"].forEach(fn => {
					frm.set_df_property(fn, "read_only", 0);
				});
			}
		}
	});
}

function setup_all_contacts_grid(frm) {
	// Ensure All Contacts section and table are ALWAYS visible to the user
	frm.set_df_property("all_contacts_section", "hidden", 0);
	frm.set_df_property("all_contacts", "hidden", 0);
	frm.set_df_property("all_contacts", "read_only", 0);

	if (frm.fields_dict.all_contacts_section && frm.fields_dict.all_contacts_section.$wrapper) {
		frm.fields_dict.all_contacts_section.$wrapper.show().css("display", "block !important");
	}
	if (frm.fields_dict.all_contacts && frm.fields_dict.all_contacts.$wrapper) {
		frm.fields_dict.all_contacts.$wrapper.show().css("display", "block !important");
	}
	if (frm.fields_dict.all_contacts && frm.fields_dict.all_contacts.grid) {
		let c_grid = frm.fields_dict.all_contacts.grid;
		c_grid.cannot_add_rows = true;
		["contact_name", "contact_phone", "contact_email", "contact_designation"].forEach(col => {
			c_grid.update_docfield_property(col, "read_only", 1);
		});
		if (c_grid.wrapper) {
			c_grid.wrapper.find(".grid-remove-rows, .grid-add-row, .grid-delete-row, .grid-duplicate-row, .grid-append-row").hide();
		}
		c_grid.refresh();
	}
}

function render_activity_timeline(frm) {
	if (frm.is_new() || !frm.doc.name) {
		if (frm.fields_dict.activity && frm.fields_dict.activity.$wrapper) {
			frm.fields_dict.activity.$wrapper.html("<div style='color:#a0aec0; font-style:italic; padding:10px;'>No activities recorded yet. Click <b>+ Follow-up</b> to log notes.</div>");
		}
		return;
	}

	if (frm.doc.activity && frm.doc.activity.trim() && frm.fields_dict.activity && frm.fields_dict.activity.$wrapper) {
		frm.fields_dict.activity.$wrapper.html(frm.doc.activity);
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_activity_html",
		args: {
			name: frm.doc.name
		},
		callback: function (r) {
			if (r.message && frm.fields_dict.activity && frm.fields_dict.activity.$wrapper) {
				frm.fields_dict.activity.$wrapper.html(r.message);
			}
		}
	});
}

function open_follow_up_dialog(frm) {
	let df = frappe.meta.get_docfield("Hbs Tally Renewal", "crm_stage");
	let stage_options = [];
	if (df && df.options) {
		stage_options = df.options.split("\n").map(s => s.trim());
	}
	if (!stage_options.length) {
		stage_options = [
			"",
			"CUSTOMER NOT RESPONDING",
			"FORWARD TO",
			"CUSTOMER REQ PENDING",
			"DEMO/MEETING DONE",
			"DEMO/ MEETING FIXED",
			"IN FOLLOW-UP",
			"LEAD",
			"NEGOTIATION",
			"PAYMENT RECEIVED",
			"PENDING FOR INSTALLATION",
			"PENDING PAYMENT",
			"QUOTATION PENDING",
			"QUOTATION SENT",
			"WAITING FOR CONFIRMATION"
		];
	}
	if (!stage_options.includes("")) stage_options.unshift("");
	if (!stage_options.includes("FORWARD TO")) stage_options.splice(2, 0, "FORWARD TO");

	let d = new frappe.ui.Dialog({
		title: __("Log Follow-up & Update Status"),
		fields: [
			{
				label: __("CRM Status"),
				fieldname: "crm_status",
				fieldtype: "Select",
				options: ["PENDING", "Sold", "Lost"],
				default: frm.doc.crm_status || "PENDING",
				reqd: 1
			},
			{
				label: __("CRM Stage"),
				fieldname: "crm_stage",
				fieldtype: "Select",
				options: stage_options,
				default: frm.doc.crm_stage || "LEAD",
				reqd: 1
			},
			{
				fieldtype: "Section Break",
				label: __("Follow-up Details")
			},
			{
				label: __("Next Follow-up Date"),
				fieldname: "follow_up_date",
				fieldtype: "Date",
				default: (frm.doc.follow_up_date && frm.doc.follow_up_date >= frappe.datetime.get_today()) ? frm.doc.follow_up_date : frappe.datetime.get_today(),
				reqd: 1
			},
			{
				label: __("Remarks / Notes"),
				fieldname: "remarks",
				fieldtype: "Small Text",
				reqd: 1
			}
		],
		primary_action_label: __("Save Follow-up"),
		primary_action(values) {
			if (values.follow_up_date && values.follow_up_date < frappe.datetime.get_today()) {
				frappe.msgprint({
					title: __("Invalid Follow-up Date"),
					indicator: "red",
					message: __("Follow-up date cannot be smaller than current date ({0}).", [frappe.datetime.str_to_user(frappe.datetime.get_today())])
				});
				return;
			}

			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.log_follow_up",
				args: {
					name: frm.doc.name,
					follow_up_date: values.follow_up_date,
					remark: values.remarks,
					crm_status: values.crm_status,
					crm_stage: values.crm_stage
				},
				freeze: true,
				freeze_message: __("Saving follow-up and status..."),
				callback: function (r) {
					if (r.message && r.message.status === "success") {
						d.hide();
						frappe.show_alert({
							message: r.message.message,
							indicator: "green"
						});
						frm.reload_doc();
					}
				}
			});
		}
	});
	d.show();
}

function open_assign_dialog(frm) {
	let d = new frappe.ui.Dialog({
		title: __("Assign Executive"),
		fields: [
			{
				label: __("Executive 1"),
				fieldname: "executive_1",
				fieldtype: "Link",
				options: "User",
				default: frm.doc.crm_ex_1 || frappe.session.user,
				reqd: 1
			}
		],
		primary_action_label: __("Assign"),
		primary_action(values) {
			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.assign_executive",
				args: {
					name: frm.doc.name,
					executive_1: values.executive_1
				},
				freeze: true,
				freeze_message: __("Assigning executive..."),
				callback: function (r) {
					if (!r.exc) {
						d.hide();
						frappe.show_alert({
							message: __("Executive assigned successfully!"),
							indicator: "green"
						});
						frm.reload_doc();
					}
				}
			});
		}
	});
	d.show();
}

function apply_custom_section_styles(frm) {
	$('#hbs-tally-renewal-custom-css').remove();
	$('head').append(`
		<style id="hbs-tally-renewal-custom-css">
			/* Card Containers for the 4 Key Columns in Person Detail Section */
			.hbs-card-col {
				border-radius: 8px !important;
				padding: 10px 14px 10px 14px !important;
				margin-bottom: 14px !important;
				transition: all 0.2s ease !important;
				box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04) !important;
			}
			.hbs-card-col:hover {
				box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
			}

			/* 1. Serial Details (Indigo Theme) */
			.hbs-card-serial {
				border: 1.5px solid #c7d2fe !important;
				border-top: 4px solid #6366f1 !important;
				background-color: #faf5ff !important;
			}
			.hbs-card-serial .hbs-card-badge {
				display: flex;
				align-items: center;
				gap: 5px;
				font-size: 11px;
				font-weight: 700;
				letter-spacing: 0.5px;
				text-transform: uppercase;
				color: #4338ca;
				background-color: #e0e7ff;
				border: 1px solid #c7d2fe;
				padding: 4px 8px;
				border-radius: 5px;
				margin-bottom: 10px;
			}
			.hbs-card-serial input,
			.hbs-card-serial select,
			.hbs-card-serial textarea,
			.hbs-card-serial .control-value,
			.hbs-card-serial .like-disabled-input {
				border: 1px solid #c7d2fe !important;
				border-radius: 6px !important;
				background-color: #ffffff !important;
			}
			.hbs-card-serial input:focus,
			.hbs-card-serial select:focus,
			.hbs-card-serial textarea:focus {
				border-color: #6366f1 !important;
				box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15) !important;
			}

			/* 2. Party Details (Ocean Blue Theme) */
			.hbs-card-party {
				border: 1.5px solid #bae6fd !important;
				border-top: 4px solid #0284c7 !important;
				background-color: #f0f9ff !important;
			}
			.hbs-card-party .hbs-card-badge {
				display: flex;
				align-items: center;
				gap: 5px;
				font-size: 11px;
				font-weight: 700;
				letter-spacing: 0.5px;
				text-transform: uppercase;
				color: #0369a1;
				background-color: #e0f2fe;
				border: 1px solid #bae6fd;
				padding: 4px 8px;
				border-radius: 5px;
				margin-bottom: 10px;
			}
			.hbs-card-party input,
			.hbs-card-party select,
			.hbs-card-party textarea,
			.hbs-card-party .control-value,
			.hbs-card-party .like-disabled-input {
				border: 1px solid #7dd3fc !important;
				border-radius: 6px !important;
				background-color: #ffffff !important;
			}
			.hbs-card-party input:focus,
			.hbs-card-party select:focus,
			.hbs-card-party textarea:focus {
				border-color: #0284c7 !important;
				box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.15) !important;
			}

			/* 3. Usage & Priority Details (Amber Theme) */
			.hbs-card-usage {
				border: 1.5px solid #fed7aa !important;
				border-top: 4px solid #f59e0b !important;
				background-color: #fffdf5 !important;
			}
			.hbs-card-usage .hbs-card-badge {
				display: flex;
				align-items: center;
				gap: 5px;
				font-size: 11px;
				font-weight: 700;
				letter-spacing: 0.5px;
				text-transform: uppercase;
				color: #b45309;
				background-color: #fef3c7;
				border: 1px solid #fed7aa;
				padding: 4px 8px;
				border-radius: 5px;
				margin-bottom: 10px;
			}
			.hbs-card-usage input,
			.hbs-card-usage select,
			.hbs-card-usage textarea,
			.hbs-card-usage .control-value,
			.hbs-card-usage .like-disabled-input {
				border: 1px solid #fde68a !important;
				border-radius: 6px !important;
				background-color: #ffffff !important;
			}
			.hbs-card-usage input:focus,
			.hbs-card-usage select:focus,
			.hbs-card-usage textarea:focus {
				border-color: #f59e0b !important;
				box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.15) !important;
			}

			/* 4. Executive Details (Emerald Theme) */
			.hbs-card-executive {
				border: 1.5px solid #a7f3d0 !important;
				border-top: 4px solid #10b981 !important;
				background-color: #f0fdf4 !important;
			}
			.hbs-card-executive .hbs-card-badge {
				display: flex;
				align-items: center;
				gap: 5px;
				font-size: 11px;
				font-weight: 700;
				letter-spacing: 0.5px;
				text-transform: uppercase;
				color: #047857;
				background-color: #d1fae5;
				border: 1px solid #a7f3d0;
				padding: 4px 8px;
				border-radius: 5px;
				margin-bottom: 10px;
			}
			.hbs-card-executive input,
			.hbs-card-executive select,
			.hbs-card-executive textarea,
			.hbs-card-executive .control-value,
			.hbs-card-executive .like-disabled-input {
				border: 1px solid #6ee7b7 !important;
				border-radius: 6px !important;
				background-color: #ffffff !important;
			}
			.hbs-card-executive input:focus,
			.hbs-card-executive select:focus,
			.hbs-card-executive textarea:focus {
				border-color: #10b981 !important;
				box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.15) !important;
			}

			/* Related Sections Accents */
			.form-page [data-fieldname="license_details_section"] {
				border-left: 4px solid #6366f1 !important;
				padding-left: 12px !important;
			}
			.form-page [data-fieldname="address_details_section"],
			.form-page [data-fieldname="executive_details_section"] {
				border-left: 4px solid #0284c7 !important;
				padding-left: 12px !important;
			}
			.form-page [data-fieldname="follow_up_section"] {
				border-left: 4px solid #10b981 !important;
				padding-left: 12px !important;
			}

			/* Base field formatting */
			.form-page input,
			.form-page select,
			.form-page textarea,
			.form-page .control-value,
			.form-page .like-disabled-input {
				border: 1px solid #d1d5db !important;
				border-radius: 6px !important;
				color: #111827 !important;
				font-weight: 500 !important;
				min-height: 28px !important;
				padding: 4px 8px !important;
			}

			.form-page input:focus,
			.form-page select:focus,
			.form-page textarea:focus {
				border-color: #2563eb !important;
				background-color: #ffffff !important;
				outline: none !important;
				box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12) !important;
			}

			/* Dynamic Bright Red for Portal Expiry Date when populated */
			.form-page [data-fieldname="portal_expiry_date"].has-portal-expiry input,
			.form-page [data-fieldname="portal_expiry_date"].has-portal-expiry .control-value,
			.form-page [data-fieldname="portal_expiry_date"].has-portal-expiry .like-disabled-input {
				border: 2px solid #ef4444 !important;
				border-radius: 6px !important;
				background-color: #fee2e2 !important;
				color: #b91c1c !important;
				font-weight: 700 !important;
				min-height: 28px !important;
				padding: 4px 8px !important;
			}

			/* 5. Pre-Call Notes / Briefing (Amber Sticky Card Theme) */
			.form-page [data-fieldname="description_section"] {
				margin-top: 14px !important;
				margin-bottom: 14px !important;
			}
			.form-page [data-fieldname="description_section"] .section-head {
				color: #92400e !important;
				font-weight: 700 !important;
			}
			.form-page [data-fieldname="notes"] {
				background: #fffdf5 !important;
				border: 1.5px solid #fed7aa !important;
				border-radius: 6px !important;
				padding: 6px 10px !important;
				margin-top: 2px !important;
				margin-bottom: 4px !important;
				box-shadow: 0 1px 3px rgba(245, 158, 11, 0.06) !important;
				transition: all 0.2s ease !important;
			}
			.form-page [data-fieldname="notes"]:hover {
				box-shadow: 0 2px 8px rgba(245, 158, 11, 0.12) !important;
				border-color: #f59e0b !important;
			}
			.form-page [data-fieldname="notes"] .control-label {
				color: #92400e !important;
				font-weight: 700 !important;
				font-size: 11px !important;
				display: flex !important;
				align-items: center !important;
				gap: 4px !important;
				margin-bottom: 3px !important;
			}
			.form-page [data-fieldname="notes"] textarea {
				background-color: #ffffff !important;
				border: 1px solid #fcd34d !important;
				border-radius: 4px !important;
				color: #1e293b !important;
				font-size: 12px !important;
				line-height: 1.35 !important;
				min-height: 38px !important;
				height: 42px !important;
				padding: 5px 8px !important;
			}
			.form-page [data-fieldname="notes"] textarea:focus {
				border-color: #f59e0b !important;
				box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2) !important;
				outline: none !important;
				background-color: #ffffff !important;
			}
			.form-page [data-fieldname="notes"] .control-value {
				background-color: #ffffff !important;
				border: 1px solid #fcd34d !important;
				border-radius: 6px !important;
				padding: 8px 10px !important;
				color: #1e293b !important;
				font-size: 13px !important;
				line-height: 1.5 !important;
				white-space: pre-wrap !important;
			}

			/* Clean Modal Dialog inputs */
			.modal-dialog input,
			.modal-dialog select,
			.modal-dialog textarea,
			.modal-dialog .control-value {
				border: 1px solid #d1d5db !important;
				background-color: #ffffff !important;
				color: #1f2937 !important;
				font-weight: 400 !important;
			}
		</style>
	`);

	// Attach visually differentiated card classes and headers to the 4 main columns
	setTimeout(() => {
		let col_configs = [
			{ field: "tss_tally_serial", cls: "hbs-card-serial", badge: "🔢 Serial & License Details" },
			{ field: "cc_acc_name", cls: "hbs-card-party", badge: "🏢 Party Details" },
			{ field: "mau", cls: "hbs-card-usage", badge: "📊 Usage & Priority" },
			{ field: "crm_ex_1", cls: "hbs-card-executive", badge: "👤 Executive Details" }
		];

		col_configs.forEach(cfg => {
			if (frm.fields_dict[cfg.field] && frm.fields_dict[cfg.field].$wrapper) {
				let $col = frm.fields_dict[cfg.field].$wrapper.closest(".form-column");
				if ($col.length) {
					$col.find(".hbs-card-ribbon").remove();
					$col.addClass("hbs-card-col " + cfg.cls);
					if (!$col.find(".hbs-card-badge").length) {
						$col.prepend(`<div class="hbs-card-badge">${cfg.badge}</div>`);
					}
				}
			}
		});

		// Pre-Call Client Notes styling & badge
		if (frm.fields_dict.notes && frm.fields_dict.notes.$wrapper) {
			let $w = frm.fields_dict.notes.$wrapper;
			let $label = $w.find(".control-label");
			if ($label.length && !$label.find(".hbs-notes-badge").length) {
				$label.html(`
					<span class="hbs-notes-badge" style="background: #fef3c7; color: #b45309; border: 1px solid #fcd34d; font-size: 11.5px; font-weight: 700; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.5px;">
						💡 Pre-Call Briefing
					</span>
				`);
			}
			let $textarea = $w.find("textarea");
			if ($textarea.length) {
				$textarea.attr(
					"placeholder",
					__("Write key talking points, client temperament, special discount/terms agreed, or things to keep in mind before speaking to this client...")
				);
			}
		}
	}, 100);

	// Dynamic toggle for Portal Expiry Date
	let has_portal_expiry = !!(frm.doc.portal_expiry_date && frm.doc.portal_expiry_date.toString().trim());
	if (frm.fields_dict.portal_expiry_date && frm.fields_dict.portal_expiry_date.$wrapper) {
		if (has_portal_expiry) {
			frm.fields_dict.portal_expiry_date.$wrapper.addClass("has-portal-expiry");
		} else {
			frm.fields_dict.portal_expiry_date.$wrapper.removeClass("has-portal-expiry");
		}
	}
}

function render_old_remarks_timeline(frm) {
	if (frm.is_new() || !frm.doc.name) {
		if (frm.fields_dict.old_remarks_html && frm.fields_dict.old_remarks_html.$wrapper) {
			frm.fields_dict.old_remarks_html.$wrapper.html("<div style='color:#94a3b8; font-style:italic; padding:10px;'>No past remarks imported yet.</div>");
		}
		return;
	}

	if (frm.doc.old_remarks_html && frm.doc.old_remarks_html.trim() && frm.fields_dict.old_remarks_html && frm.fields_dict.old_remarks_html.$wrapper) {
		frm.fields_dict.old_remarks_html.$wrapper.html(frm.doc.old_remarks_html);
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_old_remarks_html",
		args: {
			name: frm.doc.name
		},
		callback: function (r) {
			if (r.message && frm.fields_dict.old_remarks_html && frm.fields_dict.old_remarks_html.$wrapper) {
				frm.fields_dict.old_remarks_html.$wrapper.html(r.message);
			}
		}
	});
}

function open_email_dialog(frm) {
	let client_email = (frm.doc.cc_email || frm.doc.portal_email || frm.doc.admin_id || frm.doc.director_email || "").trim();

	if (!client_email) {
		frappe.msgprint({
			title: __("Client Email Required"),
			indicator: "orange",
			message: __("<b>Client Email is not set on this record!</b><br>Please enter the client's email in <b>Email ID</b> (cc_email) field, or enter it manually in the <b>To</b> field in the dialog.")
		});
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_rendered_renewal_email_template",
		args: { name: frm.doc.name },
		freeze: true,
		freeze_message: __("Loading email template..."),
		callback: function (res) {
			if (res.message) {
				let default_subject = res.message.subject;
				let default_message = res.message.message;
				let default_from = res.message.from_email;
				let default_sender = res.message.sender_name;
				let default_to = res.message.to_email || client_email;
				let default_cc = (frappe.session.user && frappe.session.user.indexOf("@") !== -1) ? frappe.session.user : (res.message.cc_email || "");

				let d = new frappe.ui.Dialog({
					title: __("Send TSS Quotation to Client - {0}", [frm.doc.cc_acc_name || frm.doc.portal_acc_name || frm.doc.cc_contact || frm.doc.portal_contact || frm.doc.tss_tally_serial || frm.doc.tally_serial || frm.doc.name]),
					size: "large",
					fields: [
						{
							label: __("Sender Name"),
							fieldname: "sender_name",
							fieldtype: "Data",
							default: default_sender,
							reqd: 1
						},
						{
							label: __("From Email"),
							fieldname: "from_email",
							fieldtype: "Data",
							default: default_from,
							reqd: 1
						},
						{
							label: __("To (Client Email)"),
							fieldname: "to_email",
							fieldtype: "Data",
							default: default_to,
							reqd: 1,
							description: __("Client's email address")
						},
						{
							label: __("CC (Executive / Internal)"),
							fieldname: "cc_email",
							fieldtype: "Data",
							default: default_cc,
							description: __("Executive email copy")
						},
						{
							label: __("Subject"),
							fieldname: "subject",
							fieldtype: "Data",
							default: default_subject,
							reqd: 1
						},
						{
							label: __("Message"),
							fieldname: "message",
							fieldtype: "Text Editor",
							default: default_message,
							reqd: 1
						},
						{
							label: __("Attach Quotation PDF (HBS Renewal Quotation)"),
							fieldname: "attach_print",
							fieldtype: "Check",
							default: 1
						}
					],
					primary_action_label: __("Send Quotation"),
					primary_action(values) {
						let do_send = function() {
							frappe.call({
								method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.send_manual_renewal_email",
								args: {
									name: frm.doc.name,
									sender_name: values.sender_name,
									from_email: values.from_email,
									to_email: values.to_email,
									cc_email: values.cc_email,
									subject: values.subject,
									message: values.message,
									attach_print: values.attach_print ? 1 : 0
								},
								freeze: true,
								freeze_message: __("Sending quotation email..."),
								callback: function (r) {
									if (!r.exc) {
										d.hide();
										frappe.show_alert({
											message: __("Email sent successfully to {0}!", [values.to_email]),
											indicator: "green"
										});
										frm.reload_doc();
									}
								}
							});
						};

						// Hard Guard: Prevent sending if 'To' is set to the logged-in executive's email
						if (frappe.session.user && values.to_email && values.to_email.trim().toLowerCase() === frappe.session.user.toLowerCase()) {
							frappe.msgprint({
								title: __("Invalid Client Email"),
								indicator: "red",
								message: __("<b>The 'To' recipient cannot be your own executive email ({0})!</b><br><br>Please enter the <b>client's email address</b> in the <b>To</b> field so the quotation is delivered to the client and traceable in the future.", [values.to_email])
							});
							return;
						}
						do_send();
					}
				});

				d.show();
				d.add_custom_action(__("📄 View Quotation"), function () {
					open_quotation_preview_dialog(frm, "Hbs Tally Renewal");
				});
			}
		}
	});
}

frappe.ui.form.on("hbs crm items", {
	item_name(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_name) {
			frappe.db.get_doc("Hbs Product", row.item_name).then((doc) => {
				frappe.model.set_value(cdt, cdn, "rate", doc.rate || 0);
				frappe.model.set_value(cdt, cdn, "description", "");
				frappe.model.set_value(cdt, cdn, "tax", doc.tax || 0);
				frappe.model.set_value(cdt, cdn, "hsn", doc.hsn || "");
				if (!row.qty) {
					frappe.model.set_value(cdt, cdn, "qty", 1);
				}
				validate_row_min_rate(frm, cdt, cdn, doc);
				calculate_item_amount(frm, cdt, cdn);
			});
		}
	},

	qty(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
	},

	rate(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_name) {
			frappe.db.get_doc("Hbs Product", row.item_name).then((doc) => {
				validate_row_min_rate(frm, cdt, cdn, doc);
				calculate_item_amount(frm, cdt, cdn);
			});
		} else {
			calculate_item_amount(frm, cdt, cdn);
		}
	},

	discount_amount(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
	},

	tax(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
	},

	items_remove(frm) {
		calculate_totals(frm);
	}
});

function calculate_item_amount(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let qty = flt(row.qty) || 1;
	let rate = flt(row.rate) || 0;
	let tax_percent = flt(row.tax) || 0;

	let subtotal = qty * rate;
	let tax_amount = (subtotal * tax_percent) / 100.0;
	let total_amount = subtotal + tax_amount;

	row.tax_amount = tax_amount;
	row.amount = total_amount;

	calculate_totals(frm);
}

function calculate_totals(frm) {
	let total_before_tax = 0;
	(frm.doc.items || []).forEach((row) => {
		let qty = flt(row.qty) || 1;
		let rate = flt(row.rate) || 0;
		total_before_tax += (qty * rate);
	});

	let total_tax = 0;

	(frm.doc.items || []).forEach((row) => {
		let qty = flt(row.qty) || 1;
		let rate = flt(row.rate) || 0;
		let row_subtotal = (qty * rate);
		let tax_percent = flt(row.tax) || 0;
		let tax_amt = (row_subtotal * tax_percent) / 100.0;
		let row_amount = row_subtotal + tax_amt;

		row.tax_amount = tax_amt;
		row.amount = row_amount;
		total_tax += tax_amt;
	});

	frm.refresh_field("items");

	let final_total = Math.round(total_before_tax + total_tax);

	frm.set_value("total_before_tax", total_before_tax);
	frm.set_value("total_tax", total_tax);
	frm.set_value("total_after_tax", total_before_tax);
	frm.set_value("final_total", final_total);
}

function auto_fill_quote_items_client(frm) {
	if (frm.doc.items && frm.doc.items.length > 0) return;
	let lic_raw = [frm.doc.license, frm.doc.flavour, frm.doc.license_type, frm.doc.tally_parent, frm.doc.edition].filter(Boolean).join(" ").toLowerCase();
	let target_name = null;
	if (lic_raw.indexOf("gold") !== -1) target_name = "TALLY SOFTWARE SERVICES GOLD";
	else if (lic_raw.indexOf("silver") !== -1) target_name = "TALLY SOFTWARE SERVICES SILVER";
	else if (lic_raw.indexOf("auditor") !== -1) target_name = "TALLY SOFTWARE SERVICES AUDITOR";

	if (!target_name) return;

	frappe.db.get_value("Hbs Product", {"item_name": target_name, "is_active": 1}, ["name", "rate", "tax", "hsn"]).then(r => {
		if (r && r.message && (!frm.doc.items || frm.doc.items.length === 0)) {
			let prod = r.message;
			let row = frm.add_child("items");
			row.item_name = prod.name;
			row.qty = 1;
			row.rate = frm.doc.cc_amount || prod.rate || 0;
			row.tax = prod.tax || 0;
			row.hsn = prod.hsn || "";
			frm.refresh_field("items");
			calculate_totals(frm);
		}
	});
}

function validate_row_min_rate(frm, cdt, cdn, product_doc) {
	let row = locals[cdt][cdn];
	let min_rate = flt(product_doc.min_rate || 0);
	let current_rate = flt(row.rate || 0);

	if (min_rate > 0 && current_rate < min_rate) {
		let item_title = product_doc.item_name || product_doc.product_name || row.item_name;
		frappe.msgprint({
			title: __("Minimum Rate Warning"),
			indicator: "orange",
			message: __("Rate for item <b>{0}</b> cannot be lower than the Minimum Allowed Rate (<b>₹{1}</b>). Auto-resetting rate to ₹{1}.", [item_title, min_rate])
		});
		frappe.model.set_value(cdt, cdn, "rate", min_rate);
	}
}

function is_genuine_tally_serial(serial) {
	if (!serial) return true;
	let s = String(serial).trim();
	if (s.length !== 9 || !/^\d+$/.test(s)) return false;
	if (!s.startsWith("7")) return false;
	let sum = s.split("").reduce((acc, d) => acc + parseInt(d, 10), 0);
	while (sum >= 10) {
		sum = String(sum).split("").reduce((acc, d) => acc + parseInt(d, 10), 0);
	}
	return sum === 9;
}

function check_and_warn_duplicate_serial(frm) {
	let serial = (frm.doc.tally_serial || frm.doc.tss_tally_serial || "").toString().trim();
	if (!serial || serial.length < 9) return;

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_duplicate_renewal",
		args: {
			serial: serial,
			current_renewal_name: frm.doc.name
		},
		callback: function (r) {
			if (r.message) {
				let dup = r.message;
				let party = dup.company_name || dup.customer_name || dup.cc_acc_name || "this party";
				let exec = dup.executive_full_name || dup.crm_ex_1 || dup.owner || "another executive";

				if (dup.is_inactive) {
					let is_lost = !!dup.is_lost;
					let title = is_lost ? __("Lost Renewal Found") : __("Dormant Renewal Found");
					let btn_label = is_lost
						? __(`⚡ Take Over & Revive Renewal (#${dup.name})`)
						: __(`⚡ Take Over & Open Renewal (#${dup.name})`);

					let msg = is_lost ? `
						<div style="padding: 10px; font-size: 14px; line-height: 1.6;">
							<p style="color: #dd6b20; font-weight: 600; font-size: 15px; margin-bottom: 8px;">
								⚠️ Lost Renewal Found for Serial <b>${serial}</b>!
							</p>
							<p>
								This renewal for <b>${party}</b> was marked as <b>Lost</b> (previously managed by <b>${exec}</b>, Renewal #${dup.name}).
							</p>
							<p style="background: #fffaf0; border: 1px solid #fbd38d; border-radius: 6px; padding: 10px; margin-top: 10px; color: #744210;">
								Lost renewals can be taken over immediately without any waiting period.
							</p>
							<p style="margin-top: 10px; color: #2d3748;">
								You can take over this renewal and revive it as pending directly.
							</p>
						</div>
					` : `
						<div style="padding: 10px; font-size: 14px; line-height: 1.6;">
							<p style="color: #dd6b20; font-weight: 600; font-size: 15px; margin-bottom: 8px;">
								⚠️ Inactive Duplicate Renewal Found (15+ Days)!
							</p>
							<p>
								A renewal for Tally Serial <b>${serial}</b> (${party}) was managed by <b>${exec}</b> (Renewal #${dup.name}).
							</p>
							<p style="background: #fffaf0; border: 1px solid #fbd38d; border-radius: 6px; padding: 10px; margin-top: 10px; color: #744210;">
								<b>No follow-up remarks</b> have been logged on this renewal for <b>${dup.days_inactive} days</b> (Last remark: ${dup.last_remarks_date_formatted || dup.creation_date}).
							</p>
							<p style="margin-top: 10px; color: #2d3748;">
								You can take over this renewal and manage it directly.
							</p>
						</div>
					`;

					let d = new frappe.ui.Dialog({
						title: title,
						indicator: "orange",
						fields: [
							{
								fieldtype: "HTML",
								fieldname: "warning_html",
								options: msg
							}
						],
						primary_action_label: btn_label,
						primary_action() {
							d.hide();
							frappe.call({
								method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.take_over_renewal",
								args: { renewal_name: dup.name },
								freeze: true,
								freeze_message: __("Taking over renewal..."),
								callback: function (res) {
									if (res.message) {
										frappe.show_alert({
											message: res.message.message,
											indicator: "green"
										});
										frappe.set_route("Form", "Hbs Tally Renewal", dup.name);
									}
								}
							});
						},
						secondary_action_label: __("Close"),
						secondary_action() {
							d.hide();
						}
					});
					d.show();
				} else {
					let msg = `
						<div style="padding: 10px; font-size: 14px; line-height: 1.6;">
							<p style="color: #c53030; font-weight: 600; font-size: 15px; margin-bottom: 8px;">
								⚠️ Active Duplicate Tally Serial Blocked!
							</p>
							<p>
								A renewal for Tally Serial <b>${serial}</b> (${party}) is currently handled by <b>${exec}</b> (Renewal #${dup.name}).
							</p>
							<p style="color: #c53030; margin-top: 10px; font-weight: 600;">
								❌ Active follow-ups are ongoing (${dup.days_inactive} days since last remark). You cannot save a duplicate renewal for this serial.
							</p>
						</div>
					`;

					let d = new frappe.ui.Dialog({
						title: __("Duplicate Tally Serial Blocked"),
						indicator: "red",
						fields: [
							{
								fieldtype: "HTML",
								fieldname: "warning_html",
								options: msg
							}
						],
						primary_action_label: __("Close"),
						primary_action() {
							d.hide();
						}
					});
					d.show();
				}
			}
		}
	});
}

function auto_sync_portal_on_open(frm) {
	if (frm._is_syncing_portal || frm._portal_synced) return;

	// Cooldown: 15 minutes (900000 ms) so it syncs once, then waits 15 mins before syncing again.
	const COOLDOWN_MS = 15 * 60 * 1000;
	let last_sync = localStorage.getItem("hbs_portal_sync_" + frm.doc.name);
	let now = Date.now();
	if (last_sync && (now - parseInt(last_sync, 10)) < COOLDOWN_MS) {
		return;
	}

	frm._is_syncing_portal = true;
	frm._portal_synced = true;
	localStorage.setItem("hbs_portal_sync_" + frm.doc.name, now.toString());

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_portal",
		args: {
			name: frm.doc.name,
			only_expiry: 1
		},
		freeze: false,
		callback: function (r) {
			frm._is_syncing_portal = false;
			if (r && r.message && r.message.status === "success") {
				if (r.message.portal_expiry_date) {
					frm.doc.portal_expiry_date = r.message.portal_expiry_date;
					frm.refresh_field("portal_expiry_date");
					update_portal_expiry_style(frm);
				}
				frappe.show_alert({
					message: __("Portal expiry synced"),
					indicator: "green"
				}, 3);
			}
		},
		error: function () {
			frm._is_syncing_portal = false;
		}
	});
}

function open_quotation_preview_dialog(frm, doctype) {
	if (frm.is_new()) {
		frappe.msgprint(__("Please save the record first before viewing quotation."));
		return;
	}

	let method_name = (doctype === "Hbs Tally Renewal" || frm.doctype === "Hbs Tally Renewal")
		? "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_renewal_quotation_html"
		: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.get_lead_quotation_html";

	frappe.call({
		method: method_name,
		args: { name: frm.doc.name },
		freeze: true,
		freeze_message: __("Generating Quotation Preview..."),
		callback: function (r) {
			if (!r || !r.message) {
				frappe.msgprint(__("Unable to load quotation preview."));
				return;
			}

			let raw_html = r.message;

			// Strip out action-banner (Print and Get PDF) if present in raw_html
			let cleaned_html = raw_html.replace(/<div class="action-banner[^>]*>[\s\S]*?<\/div>/gi, "");

			let security_tags = `
				<style>
					.action-banner, .print-hide {
						display: none !important;
						visibility: hidden !important;
					}
					.print-format-gutter {
						padding: 0 !important;
						background: transparent !important;
					}
					@media print {
						html, body, * {
							display: none !important;
							visibility: hidden !important;
						}
					}
					body {
						-webkit-user-select: none !important;
						-moz-user-select: none !important;
						-ms-user-select: none !important;
						user-select: none !important;
					}
				</style>
				<script>
					document.addEventListener('contextmenu', function(e) { e.preventDefault(); return false; });
					document.addEventListener('keydown', function(e) {
						if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
							e.preventDefault();
							e.stopPropagation();
							return false;
						}
					});
				<\/script>
			`;

			let final_html = cleaned_html;
			if (final_html.indexOf("<head>") !== -1) {
				final_html = final_html.replace("<head>", "<head>" + security_tags);
			} else {
				final_html = security_tags + final_html;
			}

			let d = new frappe.ui.Dialog({
				title: __("📄 Quotation Preview (View Only)"),
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "quotation_preview_html"
					}
				],
				primary_action_label: __("Close"),
				primary_action() {
					d.hide();
				}
			});

			d.$wrapper.addClass("quotation-preview-modal no-print-quotation-dialog");

			let preview_container = `
				<style>
					.quotation-preview-modal .modal-dialog {
						max-width: 1250px !important;
						width: 96vw !important;
						margin: 15px auto !important;
					}
					.quotation-preview-modal .modal-content {
						border-radius: 8px !important;
						box-shadow: 0 10px 30px rgba(0,0,0,0.3) !important;
					}
					.quotation-preview-modal .modal-body {
						padding: 8px !important;
					}
					@media print {
						.no-print-quotation-dialog, .no-print-quotation-dialog * {
							display: none !important;
							visibility: hidden !important;
						}
					}
					.quotation-iframe-wrapper {
						background: #334155;
						padding: 8px;
						border-radius: 6px;
						box-shadow: inset 0 2px 5px rgba(0,0,0,0.25);
					}
					.quotation-preview-iframe {
						width: 100%;
						height: 87vh;
						border: none;
						border-radius: 4px;
						background: #fff;
						display: block;
					}
				</style>
				<div class="quotation-iframe-wrapper" oncontextmenu="return false;">
					<iframe class="quotation-preview-iframe" srcdoc="${frappe.utils.escape_html(final_html)}"></iframe>
				</div>
			`;

			d.fields_dict.quotation_preview_html.$wrapper.html(preview_container);

			let iframe_el = d.fields_dict.quotation_preview_html.$wrapper.find("iframe")[0];
			if (iframe_el) {
				iframe_el.onload = function() {
					try {
						let doc = iframe_el.contentDocument || iframe_el.contentWindow.document;
						doc.addEventListener("contextmenu", function(e) { e.preventDefault(); return false; });
						doc.addEventListener("keydown", function(e) {
							if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
								e.preventDefault();
								e.stopPropagation();
								return false;
							}
						});
					} catch(err) {}
				};
			}

			let block_print = function(e) {
				if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
					e.preventDefault();
					e.stopPropagation();
					frappe.show_alert({ message: __("Printing and exporting is disabled in Quotation Preview."), indicator: "orange" }, 3);
					return false;
				}
			};

			$(window).on("keydown.block_quotation_print", block_print);
			d.onhide = function () {
				$(window).off("keydown.block_quotation_print");
			};

			d.show();
		}
	});
}

// ============================================================
// TICKETS TAB / CALL HISTORY ACCORDING TO SERIAL NUMBER
// ============================================================
function render_tickets_tab(frm) {
	const field = frm.fields_dict.tickets_html;
	if (!field || !field.$wrapper) return;

	const serialNo = (frm.doc.tally_serial || frm.doc.tss_tally_serial || "").trim();

	if (!serialNo) {
		field.$wrapper.html(
			`<div style="color: #64748b; padding: 30px; text-align: center; background: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1; margin-top: 10px;">
				<div style="font-size: 15px; font-weight: 500; margin-bottom: 6px;">No Serial Number Available</div>
				<div style="font-size: 13px;">Please add or verify the Tally Serial Number to view related support tickets.</div>
			</div>`
		);
		return;
	}

	field.$wrapper.html(
		`<div style="color: #64748b; padding: 20px; text-align: center;">
			<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
			<span style="margin-left: 8px;">Loading tickets for serial <b>${frappe.utils.escape_html(serialNo)}</b>...</span>
		</div>`
	);

	frappe.call({
		method: "hbs_ticket_system.hbs_support_system.doctype.support_ticket.support_ticket.get_call_history",
		args: {
			serial_no: serialNo
		},
		callback: function (r) {
			const rows = r.message || [];
			const esc = value => frappe.utils.escape_html(String(value || ""));

			let headerHtml = `
				<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding: 10px 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
					<div>
						<span style="font-weight: 600; font-size: 14px; color: #1e293b;">Support Tickets &amp; Call History</span>
						<span class="text-muted" style="margin-left: 8px; font-size: 12px;">Serial: <b style="color: #0f172a;">${esc(serialNo)}</b></span>
						<span class="badge badge-secondary" style="margin-left: 6px; font-size: 11px;">${rows.length} ${rows.length === 1 ? 'ticket' : 'tickets'}</span>
					</div>
					<div>
						<button type="button" class="btn btn-xs btn-primary btn-create-support-ticket" style="font-weight: 600; padding: 4px 10px;">
							+ Create Support Ticket
						</button>
					</div>
				</div>
			`;

			if (!rows.length) {
				field.$wrapper.html(
					headerHtml +
					`<div style="color: #64748b; padding: 30px; text-align: center; background: #ffffff; border-radius: 8px; border: 1px dashed #e2e8f0;">
						<div style="font-size: 14px; font-weight: 500; margin-bottom: 4px;">No support tickets found</div>
						<div style="font-size: 12px; color: #94a3b8;">No tickets have been raised for serial number ${esc(serialNo)} yet.</div>
					</div>`
				);
				bind_tickets_events(frm, field, serialNo);
				return;
			}

			function get_status_pill(status) {
				const s = String(status || "").toUpperCase();
				let color = "gray";
				if (s === "COMPLETED") color = "green";
				else if (s === "FOLLOWUP") color = "orange";
				else if (s === "NEW") color = "blue";
				else if (s === "PENDING") color = "red";
				return `<span class="indicator-pill ${color}" style="font-size: 11px; font-weight: 600;">${esc(status)}</span>`;
			}

			function format_dt(dt) {
				if (!dt) return "-";
				try {
					const d = frappe.datetime.str_to_user(dt);
					const timePart = dt.indexOf(" ") > -1 ? dt.split(" ")[1].substring(0, 5) : "";
					return timePart ? `${d} ${timePart}` : d;
				} catch (e) {
					return dt;
				}
			}

			let tableHtml = `
				${headerHtml}
				<div style="overflow-x: auto; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
					<table class="table table-bordered table-hover" style="font-size: 13px; margin-bottom: 0;">
						<thead>
							<tr style="background: #f1f5f9; color: #334155; font-weight: 600;">
								<th style="width: 140px;">Ticket No</th>
								<th>Serial No</th>
								<th>Call Source</th>
								<th>Call Type</th>
								<th>Executive 1</th>
								<th>Executive 2</th>
								<th>Status</th>
								<th style="width: 130px;">Creation Date</th>
								<th style="width: 100px; text-align: center;">Details</th>
							</tr>
						</thead>
						<tbody>
			`;

			rows.forEach(row => {
				const ticketName = esc(row.name);
				const ticketUrl = `/app/support_ticket/${encodeURIComponent(row.name)}`;

				tableHtml += `
					<tr>
						<td>
							<a href="${ticketUrl}" target="_blank" style="font-weight: 600; text-decoration: underline; color: #2563eb;">
								${ticketName}
							</a>
						</td>
						<td><b>${esc(row.serial_no || "-")}</b></td>
						<td>${esc(row.call_source || "-")}</td>
						<td>${esc(row.call_type || "-")}</td>
						<td>${esc(row.executive || "-")}</td>
						<td>${esc(row.executive2 || "-")}</td>
						<td>${get_status_pill(row.status)}</td>
						<td>${esc(format_dt(row.creation))}</td>
						<td style="text-align: center;">
							<button type="button" class="btn btn-xs btn-default view-ticket-details" data-ticket="${ticketName}">
								View Details
							</button>
						</td>
					</tr>
				`;
			});

			tableHtml += `
						</tbody>
					</table>
				</div>
			`;

			field.$wrapper.html(tableHtml);
			bind_tickets_events(frm, field, serialNo);
		}
	});
}

function bind_tickets_events(frm, field, serialNo) {
	field.$wrapper
		.off("click.createticket", ".btn-create-support-ticket")
		.on("click.createticket", ".btn-create-support-ticket", function () {
			frappe.new_doc("support_ticket", {
				serial_no: serialNo,
				party_name: frm.doc.portal_acc_name || frm.doc.cc_acc_name || "",
				contact_name: frm.doc.portal_contact || frm.doc.cc_contact || frm.doc.director_contact_person || "",
				contact_phone: frm.doc.portal_mobile || frm.doc.cc_mobile || frm.doc.portal_phone || frm.doc.cc_phone || frm.doc.director_mobile || "",
				email: frm.doc.account_id || frm.doc.portal_email || frm.doc.cc_email || ""
			});
		});

	field.$wrapper
		.off("click.viewdetails", ".view-ticket-details")
		.on("click.viewdetails", ".view-ticket-details", function () {
			const ticketName = $(this).attr("data-ticket");
			if (!ticketName) return;

			frappe.call({
				method: "hbs_ticket_system.hbs_support_system.doctype.support_ticket.support_ticket.get_ticket_followup_history",
				args: { ticket_name: ticketName },
				callback: function (r) {
					const ticket = r.message;
					if (!ticket) {
						frappe.msgprint("No follow-up history returned for " + ticketName);
						return;
					}

					const esc = value => frappe.utils.escape_html(String(value || ""));
					const history = ticket.followup_history || [];

					function format_dt(dt) {
						if (!dt) return "";
						try {
							const d = frappe.datetime.str_to_user(dt);
							const timePart = dt.indexOf(" ") > -1 ? dt.split(" ")[1].substring(0, 5) : "";
							return timePart ? `${d} ${timePart}` : d;
						} catch (e) {
							return dt;
						}
					}

					let timelineHtml = "";
					if (!history.length) {
						timelineHtml = '<div style="color: #94a3b8; font-style: italic; padding: 14px 16px; background: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1;">No follow-up history recorded yet.</div>';
					} else {
						history.sort((a, b) => {
							const dtA = a.updated_on || a.creation || "";
							const dtB = b.updated_on || b.creation || "";
							return dtB.localeCompare(dtA);
						});

						timelineHtml = '<div class="activity-timeline" style="margin-top: 15px; margin-left: 12px; margin-bottom: 20px; border-left: 2px solid #e2e8f0; padding-left: 24px; position: relative;">';
						history.forEach(row => {
							const user = esc(row.updated_by || "System");
							const dtStr = row.updated_on ? esc(format_dt(row.updated_on)) : "";
							const statusBadge = `<span style="background: #e2e8f0; color: #334155; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">${esc(row.status || "-")}</span>`;
							const callTypeBadge = row.call_type ? `<span style="background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500;">🏷️ ${esc(row.call_type)}</span>` : "";

							timelineHtml += `
								<div class="timeline-item" style="margin-bottom: 16px; position: relative;">
									<div class="timeline-badge" style="position: absolute; left: -31px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: #3b82f6; border: 2px solid #fff;"></div>
									<div style="background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
										<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
											<div>
												<span style="font-weight: 600; color: #1e293b;">${user}</span>
												<span style="color: #64748b; font-size: 12px; margin-left: 6px;">${dtStr}</span>
											</div>
											<div style="display: flex; gap: 6px;">
												${statusBadge}
												${callTypeBadge}
											</div>
										</div>
										<div style="color: #334155; font-size: 13px; line-height: 1.5; white-space: pre-wrap;">${esc(row.remarks || "No remarks")}</div>
									</div>
								</div>
							`;
						});
						timelineHtml += "</div>";
					}

					let modalContent = `
						<div style="background: var(--bg-light-gray, #f8f9fa); padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; font-size: 13px; border: 1px solid var(--border-color, #e2e8f0);">
							<div class="row">
								<div class="col-sm-4"><b>Ticket No:</b> ${esc(ticket.name)}</div>
								<div class="col-sm-4"><b>Company:</b> ${esc(ticket.party_name || "-")}</div>
								<div class="col-sm-4"><b>Status:</b> ${esc(ticket.status || "-")}</div>
							</div>
							<div class="row" style="margin-top: 6px;">
								<div class="col-sm-4"><b>Contact:</b> ${esc(ticket.contact_name || "-")} (${esc(ticket.contact_phone || "-")})</div>
								<div class="col-sm-4"><b>Executive 1:</b> ${esc(ticket.executive || "-")}</div>
								<div class="col-sm-4"><b>Executive 2:</b> ${esc(ticket.executive2 || "-")}</div>
							</div>
							${ticket.remarks ? `<div style="margin-top: 8px; padding-top: 6px; border-top: 1px dashed var(--border-color, #cbd5e1);"><b>Initial Remarks:</b> ${esc(ticket.remarks)}</div>` : ""}
						</div>
						${timelineHtml}
					`;

					const dialog = new frappe.ui.Dialog({
						title: __("Follow-up History - {0}", [ticket.name]),
						size: "extra-large",
						fields: [{ fieldtype: "HTML", fieldname: "history_html" }],
						primary_action_label: __("Close"),
						primary_action() {
							dialog.hide();
						}
					});

					dialog.fields_dict.history_html.$wrapper.html(modalContent);
					dialog.show();
				}
			});
		});
}

