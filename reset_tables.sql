-- Drop all existing tables
DROP TABLE IF EXISTS intelligence_patterns CASCADE;
DROP TABLE IF EXISTS training_samples CASCADE;
DROP TABLE IF EXISTS model_registry CASCADE;
DROP TABLE IF EXISTS threat_intelligence CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;

-- Tables will be recreated automatically by SQLAlchemy on app startup
