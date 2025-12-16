/**
 * Toast Notification System
 */

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - Type of notification: success, error, warning, info
 * @param {number} duration - Duration in milliseconds (0 = no auto-dismiss)
 */
function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('notifications');
    if (!container) {
        console.error('Notifications container not found');
        return;
    }

    // Create notification element
    const notification = createElement('div', {
        className: `notification ${type}`,
        role: 'alert'
    });

    // Icon based on type
    const icons = {
        success: `<svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
        </svg>`,
        error: `<svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
        </svg>`,
        warning: `<svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>`,
        info: `<svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
        </svg>`
    };

    // Build notification content
    const iconContainer = createElement('div', { className: 'notification-icon' });
    iconContainer.innerHTML = icons[type] || icons.info;

    const content = createElement('div', { className: 'notification-content' }, [
        createElement('div', { className: 'notification-message', textContent: message })
    ]);

    const closeBtn = createElement('button', {
        className: 'notification-close',
        'aria-label': 'Close notification',
        innerHTML: `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
        </svg>`
    });

    // Append elements
    notification.appendChild(iconContainer);
    notification.appendChild(content);
    notification.appendChild(closeBtn);

    // Add to container
    container.appendChild(notification);

    // Close handler
    const closeNotification = () => {
        notification.style.animation = 'slideOut 0.2s ease-out';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 200);
    };

    closeBtn.addEventListener('click', closeNotification);

    // Auto-dismiss
    if (duration > 0) {
        setTimeout(closeNotification, duration);
    }

    return notification;
}

// Add slideOut animation to stylesheet dynamically
if (typeof document !== 'undefined') {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}

/**
 * Shorthand functions for different notification types
 */
function showSuccess(message, duration = 5000) {
    return showNotification(message, 'success', duration);
}

function showError(message, duration = 7000) {
    return showNotification(message, 'error', duration);
}

function showWarning(message, duration = 6000) {
    return showNotification(message, 'warning', duration);
}

function showInfo(message, duration = 5000) {
    return showNotification(message, 'info', duration);
}

/**
 * Clear all notifications
 */
function clearNotifications() {
    const container = document.getElementById('notifications');
    if (container) {
        clearElement(container);
    }
}
