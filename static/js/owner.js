let mediaStream = null;

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function toggleUploadMode() {
    const selected = document.querySelector('input[name="image_source"]:checked')?.value;
    const fileBlock = document.getElementById("fileUploadBlock");
    const cameraBlock = document.getElementById("cameraBlock");
    if (!fileBlock || !cameraBlock) return;

    if (selected === "camera") {
        fileBlock.classList.add("hidden");
        cameraBlock.classList.remove("hidden");
    } else {
        fileBlock.classList.remove("hidden");
        cameraBlock.classList.add("hidden");
    }
}

function setupUploadMode() {
    document.querySelectorAll('input[name="image_source"]').forEach((radio) => {
        radio.addEventListener("change", toggleUploadMode);
    });
    toggleUploadMode();
}

function setupGeolocation() {
    const button = document.getElementById("geoBtn");
    if (!button) return;

    button.addEventListener("click", () => {
        if (!navigator.geolocation) {
            setText("geoStatus", "Geolocation API is not supported in this browser.");
            return;
        }

        setText("geoStatus", "Fetching location...");
        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                const lat = pos.coords.latitude;
                const lng = pos.coords.longitude;
                document.getElementById("lat").value = lat;
                document.getElementById("lng").value = lng;

                let placeLabel = `Lat ${lat.toFixed(5)}, Lon ${lng.toFixed(5)}`;
                try {
                    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}`;
                    const res = await fetch(url, {
                        headers: {
                            Accept: "application/json",
                        },
                    });
                    if (res.ok) {
                        const data = await res.json();
                        const addr = data.address || {};
                        const city =
                            addr.city ||
                            addr.town ||
                            addr.village ||
                            addr.hamlet ||
                            addr.county ||
                            "";
                        const state = addr.state || addr.region || "";
                        const country = addr.country || "";

                        const pretty = [city, state, country].filter(Boolean).join(", ");
                        if (pretty) placeLabel = pretty;

                        const villageInput = document.querySelector('input[name="village"]');
                        const districtInput = document.querySelector('input[name="district"]');
                        if (villageInput && city) villageInput.value = city;
                        if (districtInput) {
                            districtInput.value = addr.state_district || addr.county || state || "";
                        }
                    }
                } catch (_err) {
                    // Keep coordinate fallback if reverse geocoding is unavailable.
                }

                document.getElementById("locationLabel").value = placeLabel;
                setText("geoStatus", `Location captured: ${placeLabel}`);
            },
            (err) => {
                if (window.location.protocol !== "https:" && window.location.hostname !== "127.0.0.1" && window.location.hostname !== "localhost") {
                    setText("geoStatus", "Geolocation requires HTTPS or localhost.");
                    return;
                }
                setText("geoStatus", `Unable to fetch location (${err.message}).`);
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    });
}

async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setText("cameraStatus", "Camera API not supported in this browser.");
        return;
    }

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
        const video = document.getElementById("cameraPreview");
        video.srcObject = mediaStream;
        setText("cameraStatus", "Camera started.");
    } catch (err) {
        setText("cameraStatus", `Unable to access camera (${err.message}).`);
    }
}

function captureCameraFrame() {
    const video = document.getElementById("cameraPreview");
    const canvas = document.getElementById("cameraCanvas");
    const input = document.getElementById("cameraImageInput");

    if (!video || !video.srcObject) {
        setText("cameraStatus", "Start camera before capturing.");
        return;
    }

    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, width, height);
    input.value = canvas.toDataURL("image/png");
    setText("cameraStatus", "Photo captured and attached.");
}

function setupCamera() {
    document.getElementById("startCameraBtn")?.addEventListener("click", startCamera);
    document.getElementById("captureCameraBtn")?.addEventListener("click", captureCameraFrame);
}

function setupRevenueBreakdownToggle() {
    const button = document.getElementById("revenueToggleBtn");
    const card = document.getElementById("revenueBreakdownCard");
    if (!button || !card) return;

    button.addEventListener("click", () => {
        const isHidden = card.classList.contains("hidden");
        card.classList.toggle("hidden");
        button.textContent = isHidden ? "Hide Revenue Breakdown" : "View Revenue Breakdown";
    });
}

function setupListingTitle() {
    const typeSelect = document.querySelector('select[name="equipment_type"]');
    const formTitle = document.getElementById("listingFormTitle");
    const nameLabel = document.getElementById("listingNameLabel");
    const submitBtn = document.getElementById("listingSubmitBtn");
    const nameInput = document.getElementById("listingNameInput");
    if (!typeSelect || !formTitle || !nameLabel || !submitBtn) return;

    const update = () => {
        const selected = (typeSelect.value || "Equipment").trim();
        formTitle.textContent = `Add ${selected}`;
        nameLabel.textContent = `${selected} Name`;
        submitBtn.textContent = `Publish ${selected}`;
        if (nameInput && !nameInput.value) {
            nameInput.placeholder = `Enter ${selected.toLowerCase()} name`;
        }
    };

    typeSelect.addEventListener("change", update);
    update();
}

document.addEventListener("DOMContentLoaded", () => {
    setupUploadMode();
    setupGeolocation();
    setupCamera();
    setupRevenueBreakdownToggle();
    setupListingTitle();
});
