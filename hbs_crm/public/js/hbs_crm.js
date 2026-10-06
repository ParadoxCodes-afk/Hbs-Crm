// Copyright (c) 2026, Hbs and contributors
// HBS CRM - Global Desk Enhancements & Floating Horizontal Scrollbar

(function () {
	let floatingScrollbar = null;
	let floatingScrollContent = null;
	let activeContainer = null;
	let isSyncing = false;

	function initFloatingScrollbar() {
		if (document.getElementById("frappe-floating-h-scrollbar")) return;

		floatingScrollbar = document.createElement("div");
		floatingScrollbar.id = "frappe-floating-h-scrollbar";

		floatingScrollContent = document.createElement("div");
		floatingScrollContent.className = "frappe-floating-h-content";
		floatingScrollbar.appendChild(floatingScrollContent);

		document.body.appendChild(floatingScrollbar);

		floatingScrollbar.addEventListener("scroll", function () {
			if (isSyncing || !activeContainer) return;
			isSyncing = true;
			activeContainer.scrollLeft = floatingScrollbar.scrollLeft;
			isSyncing = false;
		});

		window.addEventListener("scroll", updateFloatingScrollbar, { passive: true });
		window.addEventListener("resize", updateFloatingScrollbar, { passive: true });

		// Mutation observer to detect list refreshes and route changes
		const observer = new MutationObserver(debounce(updateFloatingScrollbar, 50));
		observer.observe(document.body, { childList: true, subtree: true });

		if (typeof frappe !== "undefined" && frappe.router) {
			frappe.router.on("change", () => {
				setTimeout(updateFloatingScrollbar, 250);
			});
		}
	}

	function updateFloatingScrollbar() {
		if (!floatingScrollbar) return;

		// Find active, visible list view container
		const container = document.querySelector(".frappe-list .result-container:not(.hide)");
		if (!container || !container.offsetParent) {
			floatingScrollbar.style.display = "none";
			activeContainer = null;
			return;
		}

		const rect = container.getBoundingClientRect();
		const hasHorizontalOverflow = container.scrollWidth > container.clientWidth + 2;
		const windowHeight = window.innerHeight;

		// Visible in vertical viewport and its bottom is off-screen below
		const isVerticallyInView = rect.top < windowHeight && rect.bottom > 0;
		const isNativeScrollbarOffscreen = rect.bottom > windowHeight;

		if (hasHorizontalOverflow && isVerticallyInView && isNativeScrollbarOffscreen) {
			activeContainer = container;

			if (!container._hasFloatingScrollListener) {
				container._hasFloatingScrollListener = true;
				container.addEventListener("scroll", function () {
					if (isSyncing || !floatingScrollbar) return;
					isSyncing = true;
					floatingScrollbar.scrollLeft = container.scrollLeft;
					isSyncing = false;
				});

				// Enable mouse drag-to-scroll
				enableDragToScroll(container);
			}

			floatingScrollbar.style.display = "block";
			floatingScrollbar.style.left = Math.max(0, rect.left) + "px";
			floatingScrollbar.style.width = Math.min(rect.width, window.innerWidth - Math.max(0, rect.left)) + "px";
			floatingScrollContent.style.width = container.scrollWidth + "px";

			if (!isSyncing) {
				isSyncing = true;
				floatingScrollbar.scrollLeft = container.scrollLeft;
				isSyncing = false;
			}
		} else {
			floatingScrollbar.style.display = "none";
		}
	}

	function enableDragToScroll(el) {
		let isDown = false;
		let startX = 0;
		let scrollLeft = 0;

		el.addEventListener("mousedown", (e) => {
			// Only middle click or click on empty table areas/headers
			if (e.button === 1) { // Middle click
				isDown = true;
				el.style.cursor = "grabbing";
				startX = e.pageX - el.offsetLeft;
				scrollLeft = el.scrollLeft;
				e.preventDefault();
			}
		});

		window.addEventListener("mouseup", () => {
			if (isDown) {
				isDown = false;
				el.style.cursor = "";
			}
		});

		window.addEventListener("mousemove", (e) => {
			if (!isDown) return;
			e.preventDefault();
			const x = e.pageX - el.offsetLeft;
			const walk = (x - startX) * 1.5;
			el.scrollLeft = scrollLeft - walk;
		});

		// Shift + Wheel horizontal scroll support
		el.addEventListener("wheel", (e) => {
			if (e.shiftKey) {
				el.scrollLeft += e.deltaY;
				e.preventDefault();
			}
		}, { passive: false });
	}

	function debounce(func, wait) {
		let timeout;
		return function (...args) {
			clearTimeout(timeout);
			timeout = setTimeout(() => func.apply(this, args), wait);
		};
	}

	// Initialize on page load
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", initFloatingScrollbar);
	} else {
		initFloatingScrollbar();
	}

	// Also re-check on Frappe page events
	$(document).on("page-change", () => {
		setTimeout(updateFloatingScrollbar, 200);
	});
})();
