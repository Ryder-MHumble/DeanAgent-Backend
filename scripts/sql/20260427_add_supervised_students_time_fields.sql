ALTER TABLE supervised_students
ADD COLUMN IF NOT EXISTS entry_date DATE;

ALTER TABLE supervised_students
ADD COLUMN IF NOT EXISTS paper_date_floor DATE;
