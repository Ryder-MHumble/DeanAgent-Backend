-- Add student detail fields for DB-backed supervised student CRUD/import.
ALTER TABLE supervised_students
ADD COLUMN IF NOT EXISTS major VARCHAR(256);

ALTER TABLE supervised_students
ADD COLUMN IF NOT EXISTS mentor_name VARCHAR(128);
