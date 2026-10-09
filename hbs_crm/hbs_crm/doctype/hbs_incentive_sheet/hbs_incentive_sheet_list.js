// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

let default_from_date = moment().startOf("month").format("YYYY-MM-DD");
let default_to_date = moment().endOf("month").format("YYYY-MM-DD");

frappe.listview_settings["Hbs Incentive Sheet"] = {
	hide_name_column: true,
	hide_name_filter: true,
	filters: [["voucher_date", "Between", [default_from_date, default_to_date]]],
	refresh(listview) {
		if (listview.columns) {
			listview.columns = listview.columns.filter(col => !(col.df && (col.df.fieldname === "name" || col.df.label === "ID")));
		}
		if (typeof listview.lock_date_filter_tag === "function") {
			listview.lock_date_filter_tag();
		}
	},
	onload(listview) {
		if (listview.setup_columns) {
			let orig_setup_columns = listview.setup_columns.bind(listview);
			listview.setup_columns = function () {
				orig_setup_columns();
				this.columns = (this.columns || []).filter(col => !(col.df && (col.df.fieldname === "name" || col.df.label === "ID")));
			};
		}
		if (listview.columns) {
			listview.columns = listview.columns.filter(col => !(col.df && (col.df.fieldname === "name" || col.df.label === "ID")));
		}

		frappe.dom.set_style(`
			.frappe-list[data-doctype="Hbs Incentive Sheet"] .list-row-col.name,
			.list-view[data-doctype="Hbs Incentive Sheet"] .list-row-col.name,
			.frappe-list[data-doctype="Hbs Incentive Sheet"] .list-row-col[data-fieldname="name"],
			.list-view[data-doctype="Hbs Incentive Sheet"] .list-row-col[data-fieldname="name"],
			.frappe-list[data-doctype="Hbs Incentive Sheet"] .list-row-head .name,
			.list-view[data-doctype="Hbs Incentive Sheet"] .list-row-head .name,
			.frappe-list[data-doctype="Hbs Incentive Sheet"] [data-sort-by="name"] {
				display: none !important;
				visibility: hidden !important;
				width: 0 !important;
				min-width: 0 !important;
				padding: 0 !important;
				margin: 0 !important;
			}
			.filter-tag[data-locked-date="true"] .remove-filter {
				display: none !important;
				pointer-events: none !important;
			}
			.filter-box[data-fieldname="voucher_date"][data-locked-date-filter="true"] .remove-filter,
			.filter-box[data-locked-date-filter="true"] .remove-filter {
				display: none !important;
				visibility: hidden !important;
				pointer-events: none !important;
			}
		`);

		let is_admin_or_owner = has_common(frappe.user_roles || [], [
			"Administrator", "System Manager", "CRM Manager", "HBS Admin", "hbs admin", "Owner", "owner", "Hbs Owner"
		]) || frappe.session.user === "Administrator";

		// Render From Date and To Date controls in toolbar
		listview.page.main.find(".hbs-incentive-date-wrapper").remove();
		let $date_wrapper = $(`
			<div class="hbs-incentive-date-wrapper" style="display: inline-flex; align-items: center; gap: 6px; margin-right: 8px; vertical-align: middle;">
				<span style="font-size: 12px; font-weight: 600; color: var(--text-color);">📅 From:</span>
				<input type="date" class="form-control input-xs hbs-from-date-input" value="${default_from_date}" style="width: 125px; height: 28px; font-size: 12px; display: inline-block; cursor: pointer; border-radius: 4px;">
				<span style="font-size: 12px; font-weight: 600; color: var(--text-color);">To:</span>
				<input type="date" class="form-control input-xs hbs-to-date-input" value="${default_to_date}" style="width: 125px; height: 28px; font-size: 12px; display: inline-block; cursor: pointer; border-radius: 4px;">
			</div>
		`);

		if (listview.page.custom_actions) {
			listview.page.custom_actions.removeClass("hide").prepend($date_wrapper);
		} else if (listview.page.page_actions) {
			listview.page.page_actions.prepend($date_wrapper);
		}

		check_if_owner_or_admin(function (is_owner_admin) {
			if (is_owner_admin) {
				is_admin_or_owner = true;
			}
		});

		let $from_input = $date_wrapper.find(".hbs-from-date-input");
		let $to_input = $date_wrapper.find(".hbs-to-date-input");

		function on_date_change() {
			let from_val = $from_input.val() || default_from_date;
			let to_val = $to_input.val() || default_to_date;
			apply_locked_date_filter(from_val, to_val);
		}

		$from_input.on("change", on_date_change);
		$to_input.on("change", on_date_change);

		function apply_locked_date_filter(from_val, to_val) {
			if (!listview.filter_area) return;

			let fl = listview.filter_area.filter_list;
			let existing_filter = (fl?.filters || []).find(
				f => (f.fieldname === "voucher_date" || f.field?.df?.fieldname === "voucher_date")
			);

			if (existing_filter && typeof existing_filter.set_values === "function") {
				let p = existing_filter.set_values(existing_filter.doctype, "voucher_date", "Between", [from_val, to_val]);
				if (p && p.then) {
					p.then(() => {
						fl?.apply();
						lock_date_filter_tag();
					});
				} else {
					fl?.apply();
					lock_date_filter_tag();
				}
			} else {
				let existing = listview.filter_area.get() || [];
				let filtered = existing.filter(f => f[1] !== "voucher_date");
				filtered.push(["Hbs Incentive Sheet", "voucher_date", "Between", [from_val, to_val]]);
				listview.filter_area.clear(false).then(() => {
					return listview.filter_area.add(filtered);
				}).then(() => {
					lock_date_filter_tag();
				});
			}
		}

		function ensure_and_lock_popover_date_filter() {
			let $popover = $(".filter-popover:visible");
			if (!$popover.length) return;

			let from_val = $from_input.val() || default_from_date;
			let to_val = $to_input.val() || default_to_date;

			// 1. Remove empty/dummy ID (name) filter box if Frappe auto-added it
			$popover.find(".filter-box").each(function () {
				let $box = $(this);
				let field_val = ($box.find(".fieldname-select-area input").val() || "").trim();
				let input_val = ($box.find(".filter-field input").val() || "").trim();
				if ((field_val === "ID" || field_val === "name") && !input_val) {
					$box.remove();
				}
			});

			let fl = listview.filter_area?.filter_list;

			// 2. Deduplicate in fl.filters (ensure only ONE voucher_date filter object exists)
			if (fl && fl.filters) {
				let date_filters = fl.filters.filter(
					f => (f.fieldname === "voucher_date" || f.field?.df?.fieldname === "voucher_date")
				);
				if (date_filters.length > 1) {
					for (let i = 1; i < date_filters.length; i++) {
						let f_rem = date_filters[i];
						if (f_rem.filter_edit_area) f_rem.filter_edit_area.remove();
						let idx = fl.filters.indexOf(f_rem);
						if (idx !== -1) fl.filters.splice(idx, 1);
					}
				}
			}

			// 3. Locate all date filter boxes in popover DOM and deduplicate
			let $date_boxes = [];
			$popover.find(".filter-box").each(function () {
				let $box = $(this);
				let field_val = ($box.find(".fieldname-select-area input").val() || "").trim().toLowerCase();
				let fn = $box.attr("data-fieldname") || "";
				if (fn === "voucher_date" || field_val === "date" || field_val.includes("voucher")) {
					$date_boxes.push($box);
				}
			});

			// If duplicate date boxes exist in DOM, keep only the first and remove extras
			if ($date_boxes.length > 1) {
				for (let i = 1; i < $date_boxes.length; i++) {
					$date_boxes[i].remove();
				}
				$date_boxes = [$date_boxes[0]];
			}

			let $date_box = $date_boxes[0] || null;
			let date_filter = (fl?.filters || []).find(
				f => (f.fieldname === "voucher_date" || f.field?.df?.fieldname === "voucher_date")
			);

			// Only create/render if no date box exists at all
			if (!$date_box || !$date_box.length) {
				if (date_filter) {
					if (!date_filter.filter_edit_area || !date_filter.filter_edit_area.parent().length) {
						date_filter.parent = $popover;
						date_filter.field = null;
						date_filter.make();
					}
					$date_box = date_filter.filter_edit_area;
				} else if (fl && typeof fl.add_filter === "function") {
					fl.add_filter("Hbs Incentive Sheet", "voucher_date", "Between", [from_val, to_val]);
					return;
				}
			}

			// 4. Sync inputs and condition inside popover
			if ($date_box && $date_box.length) {
				$date_box.attr("data-fieldname", "voucher_date");
				let $cond = $date_box.find("select.condition");
				if ($cond.length && $cond.val() !== "Between") {
					$cond.val("Between");
				}

				let formatted_range = frappe.datetime.str_to_user(from_val, false, true) + " to " + frappe.datetime.str_to_user(to_val, false, true);
				let $input = $date_box.find(".filter-field input");
				if ($input.length && (!$input.val() || $input.val() !== formatted_range)) {
					$input.val(formatted_range);
				}

				// 5. If executive (not admin/owner), lock this filter box
				if (!is_admin_or_owner) {
					$date_box.attr("data-locked-date-filter", "true");
					$date_box.find(".remove-filter").remove();
					$date_box.find(".fieldname-select-area").css({
						"pointer-events": "none",
						"cursor": "not-allowed"
					});
					$date_box.find(".fieldname-select-area input").prop("disabled", true).css({
						"background-color": "var(--control-bg, #f4f5f6)",
						"cursor": "not-allowed"
					});
				}
			}

			// Also intercept date_filter.remove on JS object level
			if (date_filter && !date_filter._hbs_date_locked) {
				date_filter._hbs_date_locked = true;
				let orig_f_remove = date_filter.remove ? date_filter.remove.bind(date_filter) : null;
				date_filter.remove = function (force) {
					if (!force && !is_admin_or_owner) {
						frappe.show_alert({
							message: __("Date filter cannot be removed."),
							indicator: "orange"
						});
						return;
					}
					if (orig_f_remove) return orig_f_remove(force);
				};
			}
		}

		function lock_date_filter_tag() {
			if (!is_admin_or_owner) {
				setTimeout(() => {
					let $wrapper = $(listview.page.wrapper);
					$wrapper.find(".filter-tag").each(function () {
						let $tag = $(this);
						let text = ($tag.find(".toggle-filter").text() || "").trim().toLowerCase();
						if (text.includes("date") || text.includes("voucher_date")) {
							$tag.attr("data-locked-date", "true");
							$tag.find(".remove-filter").remove();
							$tag.find(".toggle-filter").css({
								"border-top-right-radius": "var(--border-radius)",
								"border-bottom-right-radius": "var(--border-radius)"
							});
						}
					});
					ensure_and_lock_popover_date_filter();
				}, 30);
			}

			// Sync toolbar inputs with active voucher_date filter if present
			if (listview.filter_area) {
				let filters = listview.filter_area.get() || [];
				let vf = filters.find(f => f[1] === "voucher_date" && (f[2] === "Between" || f[2] === "between"));
				if (vf && Array.isArray(vf[3]) && vf[3].length >= 2) {
					$from_input.val(vf[3][0]);
					$to_input.val(vf[3][1]);
				}
			}
		}

		listview.lock_date_filter_tag = lock_date_filter_tag;

		$(document).on("shown.bs.popover", function () {
			let route = frappe.get_route ? frappe.get_route() : null;
			if (route && route[1] === "Hbs Incentive Sheet") {
				setTimeout(ensure_and_lock_popover_date_filter, 30);
			}
		});

		listview.page.wrapper.on("click", ".filter-button, .toggle-filter", function () {
			setTimeout(ensure_and_lock_popover_date_filter, 30);
		});

		if (!window._hbs_incentive_capture_listener_attached) {
			window._hbs_incentive_capture_listener_attached = true;
			document.addEventListener("click", function (e) {
				let route = frappe.get_route ? frappe.get_route() : null;
				if (!route || route[1] !== "Hbs Incentive Sheet") return;
				if (has_common(frappe.user_roles || [], [
					"Administrator", "System Manager", "CRM Manager", "HBS Admin", "hbs admin", "Owner", "owner", "Hbs Owner"
				]) || frappe.session.user === "Administrator") return;

				let removeBtn = e.target.closest ? e.target.closest(".remove-filter") : null;
				if (!removeBtn) return;

				let box = removeBtn.closest ? removeBtn.closest(".filter-box") : null;
				let tag = removeBtn.closest ? removeBtn.closest(".filter-tag") : null;
				let isLocked = false;

				if (box) {
					let inputVal = (box.querySelector(".fieldname-select-area input")?.value || "").trim().toLowerCase();
					isLocked = box.getAttribute("data-locked-date-filter") === "true" ||
						box.getAttribute("data-fieldname") === "voucher_date" ||
						inputVal.includes("date");
				} else if (tag) {
					let tagText = (tag.querySelector(".toggle-filter")?.textContent || "").trim().toLowerCase();
					isLocked = tag.getAttribute("data-locked-date") === "true" ||
						tagText.includes("date");
				}

				if (isLocked) {
					e.preventDefault();
					e.stopPropagation();
					e.stopImmediatePropagation();
					frappe.show_alert({
						message: __("Date filter cannot be removed."),
						indicator: "orange"
					});
					return false;
				}
			}, true);
		}

		if (!is_admin_or_owner && listview.filter_area) {
			if (listview.filter_area.filter_list) {
				let fl = listview.filter_area.filter_list;
				let orig_fl_clear = fl.clear_filters.bind(fl);
				fl.clear_filters = function () {
					let from_val = $from_input.val() || default_from_date;
					let to_val = $to_input.val() || default_to_date;
					let date_filter = this.filters.find(f => (f.fieldname === "voucher_date" || f.field?.df?.fieldname === "voucher_date"));
					this.filters.forEach(f => {
						if (f !== date_filter) {
							f.remove(true);
						}
					});
					if (date_filter) {
						this.filters = [date_filter];
						date_filter.set_values(date_filter.doctype, "voucher_date", "Between", [from_val, to_val]);
					} else {
						this.filters = [];
						this.add_filter("Hbs Incentive Sheet", "voucher_date", "Between", [from_val, to_val]);
					}
					ensure_and_lock_popover_date_filter();
				};
			}

			let orig_remove = listview.filter_area.remove.bind(listview.filter_area);
			listview.filter_area.remove = function (fieldname) {
				if (fieldname === "voucher_date") {
					frappe.show_alert({
						message: __("Date filter cannot be removed."),
						indicator: "orange"
					});
					return Promise.resolve();
				}
				let res = orig_remove(fieldname);
				lock_date_filter_tag();
				return res;
			};
		}

		// Initial load: ensure Between date filter is set and rendered
		setTimeout(() => {
			let current_filters = listview.filter_area ? listview.filter_area.get() : [];
			let has_date_filter = current_filters.some(f => f[1] === "voucher_date");
			if (!has_date_filter) {
				apply_locked_date_filter(default_from_date, default_to_date);
			} else {
				lock_date_filter_tag();
			}
		}, 100);
	}
};

function check_if_owner_or_admin(callback) {
	if (frappe.session.user === "Administrator" || frappe.user.has_role("System Manager")) {
		callback(true);
		return;
	}
	if (window._hbs_user_hierarchy_info !== undefined) {
		callback(window._hbs_user_hierarchy_info.is_owner_or_admin);
		return;
	}
	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_user_hierarchy_role",
		callback: function (r) {
			let is_allowed = !!(r.message && r.message.is_owner_or_admin);
			callback(is_allowed);
		}
	});
}
