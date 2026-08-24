-- Migration to add email to scheduled_tasks channel check constraint
ALTER TABLE scheduled_tasks 
DROP CONSTRAINT IF EXISTS scheduled_tasks_channel_check;

ALTER TABLE scheduled_tasks 
ADD CONSTRAINT scheduled_tasks_channel_check CHECK (channel IN ('telegram', 'web', 'email'));
