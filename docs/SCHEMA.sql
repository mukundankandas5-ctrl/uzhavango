-- UzhavanGo SQLite/PostgreSQL friendly schema (production-ready)

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(10) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(24) NOT NULL,
    is_verified_owner BOOLEAN NOT NULL DEFAULT FALSE,
    is_active_user BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tractors (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(140) NOT NULL,
    description TEXT,
    price_per_hour NUMERIC(10,2) NOT NULL,
    image_path VARCHAR(500),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    location_label VARCHAR(255),
    pincode VARCHAR(6) NOT NULL,
    village VARCHAR(120),
    district VARCHAR(120),
    equipment_type VARCHAR(24) NOT NULL DEFAULT 'Tractor',
    availability_status VARCHAR(24) NOT NULL DEFAULT 'available',
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    rating_avg NUMERIC(3,2) NOT NULL DEFAULT 0,
    average_rating NUMERIC(3,2) NOT NULL DEFAULT 0,
    rating_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE bookings (
    id BIGSERIAL PRIMARY KEY,
    tractor_id BIGINT NOT NULL REFERENCES tractors(id) ON DELETE CASCADE,
    farmer_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    hours INTEGER NOT NULL CHECK(hours > 0),
    quoted_price_per_hour NUMERIC(10,2) NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL,
    surge_multiplier NUMERIC(5,2) NOT NULL DEFAULT 1.00,
    commission_pct NUMERIC(5,2) NOT NULL DEFAULT 10.00,
    commission_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    owner_payout_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    shared_group_code VARCHAR(32),
    accepted_at TIMESTAMPTZ,
    en_route_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    farmer_confirmed_at TIMESTAMPTZ,
    completion_confirmed_hours INTEGER,
    paid_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    farmer_note TEXT,
    owner_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE platform_settings (
    key VARCHAR(64) PRIMARY KEY,
    value VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE booking_participants (
    id BIGSERIAL PRIMARY KEY,
    booking_id BIGINT NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    farmer_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    split_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_booking_participant UNIQUE (booking_id, farmer_id)
);

CREATE TABLE chat_messages (
    id BIGSERIAL PRIMARY KEY,
    booking_id BIGINT NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    sender_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE reviews (
    id BIGSERIAL PRIMARY KEY,
    tractor_id BIGINT NOT NULL REFERENCES tractors(id) ON DELETE CASCADE,
    farmer_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_review_tractor_farmer UNIQUE (tractor_id, farmer_id)
);

CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    booking_id BIGINT NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,
    receipt_number VARCHAR(32) NOT NULL UNIQUE,
    amount NUMERIC(12,2) NOT NULL,
    farmer_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payment_status VARCHAR(24) NOT NULL DEFAULT 'paid',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(180) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_tractors_owner_available ON tractors(owner_id, is_available);
CREATE INDEX ix_tractors_pincode ON tractors(pincode);
CREATE INDEX ix_tractors_equipment_type ON tractors(equipment_type);
CREATE INDEX ix_tractors_availability_status ON tractors(availability_status);
CREATE INDEX ix_bookings_farmer_status ON bookings(farmer_id, status);
CREATE INDEX ix_bookings_tractor_status ON bookings(tractor_id, status);
CREATE INDEX ix_bookings_owner_status ON bookings(owner_id, status);
CREATE INDEX ix_payments_owner ON payments(owner_id);
CREATE INDEX ix_notifications_user_unread ON notifications(user_id, is_read);
CREATE INDEX ix_chat_messages_booking ON chat_messages(booking_id, created_at);
