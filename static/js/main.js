document.querySelectorAll("[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
        const submit = form.querySelector('button[type="submit"]');
        if (!submit) return;
        submit.disabled = true;
        const label = submit.getAttribute("data-loading-label");
        if (label) submit.textContent = label;
    });
});

function initNotificationDrawer() {
    const bell = document.getElementById("notifBellBtn");
    const drawer = document.getElementById("notifDrawer");
    if (!bell || !drawer) return;

    bell.addEventListener("click", (e) => {
        e.stopPropagation();
        const willOpen = !drawer.classList.contains("open");
        drawer.classList.toggle("open");
        if (willOpen) {
            fetch("/api/v1/notifications/me/read", { method: "POST" }).catch(() => {});
        }
    });

    document.addEventListener("click", (e) => {
        if (!drawer.contains(e.target) && e.target !== bell) {
            drawer.classList.remove("open");
        }
    });
}

function initStarPickers() {
    document.querySelectorAll(".star-picker").forEach((picker) => {
        const input = picker.closest("form")?.querySelector(".rating-input");
        if (!input) return;

        const stars = [...picker.querySelectorAll(".star-btn")];
        let value = parseInt(picker.dataset.initial || input.value || "0", 10);

        const paint = () => {
            stars.forEach((star, idx) => {
                const active = idx < value;
                star.classList.toggle("filled", active);
                star.textContent = active ? "★" : "☆";
            });
        };

        stars.forEach((star) => {
            star.addEventListener("click", () => {
                value = parseInt(star.dataset.value, 10);
                input.value = value;
                paint();
                star.classList.add("pop");
                setTimeout(() => star.classList.remove("pop"), 180);
            });
        });

        paint();
    });
}

function animateCount(el, target, opts = {}) {
    if (!el) return;
    const duration = opts.duration || 1200;
    const decimals = opts.decimals || 0;
    const start = 0;
    const startAt = performance.now();

    function tick(now) {
        const progress = Math.min((now - startAt) / duration, 1);
        const value = start + (target - start) * progress;
        el.textContent = decimals > 0 ? value.toFixed(decimals) : Math.floor(value).toLocaleString();
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

function initPlatformStats() {
    const panel = document.getElementById("platformStatsPanel");
    if (!panel) return;

    fetch("/api/platform-stats")
        .then((res) => res.json())
        .then((stats) => {
            const avg = Number(stats.average_rating || 0);
            const owners = Number(stats.verified_owners || 0);
            const bookings = Number(stats.total_bookings || 0);
            const villages = Number(stats.villages_served || 0);

            animateCount(panel.querySelector('[data-stat=\"average_rating\"]'), avg, { decimals: 1, duration: 1000 });
            animateCount(panel.querySelector('[data-stat=\"verified_owners\"]'), owners, { duration: 1200 });
            animateCount(panel.querySelector('[data-stat=\"total_bookings\"]'), bookings, { duration: 1300 });
            animateCount(panel.querySelector('[data-stat=\"villages_served\"]'), villages, { duration: 1100 });
            panel.classList.add("fade-in");
        })
        .catch(() => {
            panel.classList.add("fade-in");
        });
}

function initLocalitySearch() {
    const form = document.getElementById("localitySearchForm");
    const input = document.getElementById("localityInput");
    const results = document.getElementById("searchResults");
    const empty = document.getElementById("searchEmpty");
    const hint = document.getElementById("searchHint");
    const template = document.getElementById("tractorResultTemplate");
    const useLocationBtn = document.getElementById("useLocationBtn");
    const loading = document.getElementById("searchLoading");
    const meta = document.getElementById("searchMeta");
    const demandAlert = document.getElementById("demandAlert");
    const weatherAlert = document.getElementById("weatherAlert");
    const equipmentChips = document.getElementById("equipmentChips");
    const addonsOnlyToggle = document.getElementById("addonsOnlyToggle");
    let selectedEquipment = "";
    let listingMode = "all";
    if (!form || !input || !results || !empty || !hint || !template) return;

    const resetStates = () => {
        results.innerHTML = "";
        empty.classList.add("hidden");
        meta?.classList.add("hidden");
        demandAlert?.classList.add("hidden");
        weatherAlert?.classList.add("hidden");
        if (loading) loading.classList.add("hidden");
    };

    const renderTractors = (response) => {
        resetStates();
        hint.classList.add("hidden");
        const tractors = Array.isArray(response) ? response : response.tractors || [];
        if (!Array.isArray(response) && meta && response.message) {
            meta.textContent = response.message;
            meta.classList.remove("hidden");
        }
        if (!Array.isArray(response) && demandAlert && response.high_demand) {
            demandAlert.textContent = "High demand in your area. Surge pricing may apply.";
            demandAlert.classList.remove("hidden");
        }
        if (!Array.isArray(response) && weatherAlert && response.weather_alert) {
            weatherAlert.textContent = response.weather_alert;
            weatherAlert.classList.remove("hidden");
        }
        const equipmentLabel = !Array.isArray(response) ? response.equipment_label : "";
        if (!Array.isArray(tractors) || tractors.length === 0) {
            empty.textContent = equipmentLabel
                ? `No ${String(equipmentLabel).toLowerCase()} available in this locality yet.`
                : "No tractors available in your area yet.";
            empty.classList.remove("hidden");
            return;
        }

        tractors.forEach((tractor) => {
            const node = template.content.cloneNode(true);
            const image = node.querySelector(".search-card-image");
            const title = node.querySelector(".search-title");
            const price = node.querySelector(".search-price");
            const location = node.querySelector(".search-location");
            const rating = node.querySelector(".search-rating");
            const bookBtn = node.querySelector("a.btn.black");

            image.src = tractor.image ? `/static/${tractor.image}` : "";
            image.alt = tractor.name || "Tractor";
            if (!tractor.image) {
                image.style.display = "none";
            }

            title.textContent = tractor.name || "Tractor";
            price.textContent = `₹${tractor.price}/hour`;
            location.textContent = `Pincode: ${tractor.pincode || "N/A"}`;
            const distance = tractor.distance_km ? ` | ${tractor.distance_km} km away` : "";
            const status = tractor.status ? ` | ${tractor.status}` : "";
            const badges = Array.isArray(tractor.badges) && tractor.badges.length ? ` | ${tractor.badges.join(" • ")}` : "";
            rating.textContent = `Average Rating: ${tractor.rating || 0}${distance}${status}${badges}`;
            if (window.isFarmerLoggedIn) {
                bookBtn.href = `/tractor/${tractor.tractor_id}`;
                bookBtn.textContent = "Book";
            } else {
                bookBtn.href = window.loginUrl;
            }

            results.appendChild(node);
        });
    };

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const raw = (input.value || "").trim();
        resetStates();
        if (!raw) {
            hint.classList.remove("hidden");
            return;
        }
        if (!/^\d{6}$/.test(raw)) {
            empty.textContent = "Please enter a valid 6-digit pincode.";
            empty.classList.remove("hidden");
            return;
        }

        try {
            const response = await fetch(`/tractors?pincode=${encodeURIComponent(raw)}&equipment_type=${encodeURIComponent(selectedEquipment)}&listing_mode=${encodeURIComponent(listingMode)}`);
            const data = await response.json();
            renderTractors(data);
        } catch (_err) {
            empty.textContent = "No tractors available in this locality yet.";
            empty.classList.remove("hidden");
        }
    });

    equipmentChips?.querySelectorAll(".chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            selectedEquipment = chip.dataset.equipment || "";
            equipmentChips.querySelectorAll(".chip").forEach((el) => el.classList.remove("active"));
            chip.classList.add("active");
        });
    });

    addonsOnlyToggle?.addEventListener("change", () => {
        listingMode = addonsOnlyToggle.checked ? "addon" : "all";
    });

    if (useLocationBtn) {
        useLocationBtn.addEventListener("click", () => {
            if (!navigator.geolocation) {
                empty.textContent = "Location access denied. Please enter pincode manually.";
                empty.classList.remove("hidden");
                return;
            }
            resetStates();
            hint.classList.add("hidden");
            if (loading) loading.classList.remove("hidden");

            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    try {
                        const response = await fetch("/location-search", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                latitude: position.coords.latitude,
                                longitude: position.coords.longitude,
                                equipment_type: selectedEquipment,
                                listing_mode: listingMode,
                            }),
                        });
                        const data = await response.json();
                        if (!response.ok) {
                            empty.textContent = data.error || "Unable to detect pincode.";
                            empty.classList.remove("hidden");
                            if (loading) loading.classList.add("hidden");
                            return;
                        }
                        input.value = data.pincode || "";
                        renderTractors(data);
                    } catch (_err) {
                        if (loading) loading.classList.add("hidden");
                        empty.textContent = "Unable to detect pincode.";
                        empty.classList.remove("hidden");
                    }
                },
                () => {
                    if (loading) loading.classList.add("hidden");
                    empty.textContent = "Location access denied. Please enter pincode manually.";
                    empty.classList.remove("hidden");
                }
            );
        });
    }
}

function initAddonBookingForms() {
    document.querySelectorAll(".booking-form").forEach((form) => {
        const hoursInput = form.querySelector(".hours-input");
        const hiddenInput = form.querySelector(".addon-quantities-input");
        const baseEl = form.querySelector(".base-total");
        const addonEl = form.querySelector(".addon-total");
        const feeEl = form.querySelector(".fee-total");
        const grandEl = form.querySelector(".grand-total");
        if (!hoursInput || !hiddenInput || !baseEl || !addonEl || !feeEl || !grandEl) return;

        const baseRate = Number(form.dataset.basePrice || 0);
        const commissionPct = Number(form.dataset.commissionPct || 0);
        const quantities = {};

        const recalc = () => {
            const hours = Math.max(1, Number(hoursInput.value || 1));
            const base = baseRate * hours;
            let addon = 0;
            form.querySelectorAll(".addon-card").forEach((card) => {
                const addonId = card.dataset.addonId;
                const price = Number(card.dataset.addonPrice || 0);
                const qty = Number(quantities[addonId] || 0);
                addon += price * hours * qty;
            });
            const subtotal = base + addon;
            const fee = subtotal * (commissionPct / 100);
            const grand = subtotal;

            baseEl.textContent = `₹${base.toFixed(2)}`;
            addonEl.textContent = `₹${addon.toFixed(2)}`;
            feeEl.textContent = `₹${fee.toFixed(2)}`;
            grandEl.textContent = `₹${grand.toFixed(2)}`;

            const compact = {};
            Object.keys(quantities).forEach((key) => {
                if (Number(quantities[key]) > 0) compact[key] = Number(quantities[key]);
            });
            hiddenInput.value = JSON.stringify(compact);
        };

        form.querySelectorAll(".addon-card").forEach((card) => {
            const addonId = card.dataset.addonId;
            const qtyEl = card.querySelector(".addon-qty");
            const plusBtn = card.querySelector(".addon-plus");
            const minusBtn = card.querySelector(".addon-minus");
            quantities[addonId] = 0;

            const paint = () => {
                const qty = Number(quantities[addonId] || 0);
                qtyEl.textContent = String(qty);
                card.classList.toggle("selected", qty > 0);
                recalc();
            };

            plusBtn?.addEventListener("click", () => {
                quantities[addonId] = Number(quantities[addonId] || 0) + 1;
                paint();
            });
            minusBtn?.addEventListener("click", () => {
                quantities[addonId] = Math.max(0, Number(quantities[addonId] || 0) - 1);
                paint();
            });

            paint();
        });

        hoursInput.addEventListener("input", recalc);
        recalc();
    });
}

setTimeout(() => {
    document.querySelectorAll(".toast").forEach((el) => {
        el.style.transition = "opacity 0.4s ease";
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 400);
    });
}, 2600);

document.addEventListener("DOMContentLoaded", () => {
    initNotificationDrawer();
    initStarPickers();
    initPlatformStats();
    initLocalitySearch();
    initAddonBookingForms();
});
