-- Recent errors
SELECT timestamp, message, event->>'error_code' as code
FROM logs
WHERE level = 'ERROR'
ORDER BY timestamp DESC
LIMIT 20;

-- Request volume by hour
SELECT
    date_trunc('hour', timestamp) as hour,
    COUNT(*) as requests
FROM logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY 1
ORDER BY 1;

-- Slowest requests (if latency logged)
SELECT
    event->>'path' as path,
    AVG((event->>'latency_ms')::float) as avg_latency
FROM logs
WHERE event->>'latency_ms' IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10;
