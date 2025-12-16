-- Initialize databases for ML News Categorization services

-- Create databases for each service
CREATE DATABASE mlnews_feedback;
CREATE DATABASE mlnews_model;
CREATE DATABASE mlnews_evaluation;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE mlnews_feedback TO mlnews;
GRANT ALL PRIVILEGES ON DATABASE mlnews_model TO mlnews;
GRANT ALL PRIVILEGES ON DATABASE mlnews_evaluation TO mlnews;
