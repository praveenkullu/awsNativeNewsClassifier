/**
 * Data Formatting Utilities
 */

/**
 * Format a date/timestamp to readable string
 */
function formatDate(timestamp) {
    if (!timestamp) return '--';

    const date = new Date(timestamp);

    // Check if valid date
    if (isNaN(date.getTime())) return '--';

    const now = new Date();
    const diff = now - date;

    // Less than 1 minute
    if (diff < 60000) {
        return 'Just now';
    }

    // Less than 1 hour
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    }

    // Less than 24 hours
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }

    // Less than 7 days
    if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return `${days} day${days > 1 ? 's' : ''} ago`;
    }

    // Format as date
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Format a percentage value
 */
function formatPercentage(value, decimals = 1) {
    if (value === null || value === undefined || isNaN(value)) return '0%';

    const percentage = typeof value === 'number' ? value * 100 : parseFloat(value) * 100;
    return `${percentage.toFixed(decimals)}%`;
}

/**
 * Format duration in milliseconds
 */
function formatDuration(milliseconds) {
    if (!milliseconds || milliseconds < 0) return '0ms';

    if (milliseconds < 1000) {
        return `${Math.round(milliseconds)}ms`;
    }

    if (milliseconds < 60000) {
        return `${(milliseconds / 1000).toFixed(1)}s`;
    }

    const minutes = Math.floor(milliseconds / 60000);
    const seconds = Math.floor((milliseconds % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
}

/**
 * Format a number with separators
 */
function formatNumber(value, decimals = 0) {
    if (value === null || value === undefined || isNaN(value)) return '0';

    const num = typeof value === 'number' ? value : parseFloat(value);

    if (decimals > 0) {
        return num.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    return num.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format a file size in bytes
 */
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));

    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

/**
 * Truncate text to specified length
 */
function truncate(text, length = 50, suffix = '...') {
    if (!text || text.length <= length) return text;

    return text.substring(0, length).trim() + suffix;
}

/**
 * Capitalize first letter of a string
 */
function capitalize(text) {
    if (!text) return '';
    return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

/**
 * Convert snake_case to Title Case
 */
function snakeToTitle(text) {
    if (!text) return '';

    return text
        .split('_')
        .map(word => capitalize(word))
        .join(' ');
}

/**
 * Format ISO timestamp to local time
 */
function formatLocalTime(isoString) {
    if (!isoString) return '--';

    const date = new Date(isoString);
    if (isNaN(date.getTime())) return '--';

    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

/**
 * Format a metric value
 */
function formatMetric(value, decimals = 3) {
    if (value === null || value === undefined || isNaN(value)) return '--';

    const num = typeof value === 'number' ? value : parseFloat(value);
    return num.toFixed(decimals);
}
