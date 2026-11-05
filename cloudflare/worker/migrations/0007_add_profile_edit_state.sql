ALTER TABLE users ADD COLUMN pending_profile_field TEXT
    CHECK (pending_profile_field IN ('display_name', 'academic_year', 'department'));
