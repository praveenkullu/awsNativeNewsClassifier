/**
 * Health Monitor Component
 * Displays system health status
 */
class HealthComponent {
    constructor(apiClient) {
        this.api = apiClient;
        this.container = $('health-status');
        this.refreshBtn = $('refresh-health');
        this.autoRefreshStatus = $('auto-refresh-status');
        this.pollingInterval = null;
        this.isAutoRefreshEnabled = true;

        this.init();
    }

    async init() {
        if (!this.container) return;

        // Refresh button
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => {
                this.loadHealth();
            });
        }

        // Load initial health
        await this.loadHealth();

        // Start auto-refresh
        this.startPolling();
    }

    async loadHealth() {
        if (!this.container) return;

        try {
            const health = await this.api.getHealth();

            this.displayHealth(health);

            // Update last updated time
            this.updateLastUpdated();

            // Update API status in footer
            this.updateAPIStatus('connected');

        } catch (error) {
            console.error('Failed to load health:', error);

            this.showError(error);

            // Update API status in footer
            this.updateAPIStatus('error');
        }
    }

    displayHealth(health) {
        if (!this.container) return;

        clearElement(this.container);

        // Create health grid
        const healthGrid = createElement('div', { className: 'health-grid' });

        // API Gateway (self)
        const gatewayCard = this.createHealthCard(
            'API Gateway',
            health.status,
            {
                version: health.version,
                timestamp: health.timestamp
            }
        );
        healthGrid.appendChild(gatewayCard);

        // All dependencies
        if (health.dependencies) {
            Object.entries(health.dependencies).forEach(([serviceName, serviceStatus]) => {
                const card = this.createHealthCard(
                    this.formatServiceName(serviceName),
                    serviceStatus
                );
                healthGrid.appendChild(card);
            });
        }

        this.container.appendChild(healthGrid);
    }

    createHealthCard(serviceName, status, metadata = {}) {
        const card = createElement('div', {
            className: `health-card ${status}`
        });

        // Header
        const header = createElement('div', { className: 'health-header' });

        // Icon based on status
        const icon = createElement('div', {
            className: 'health-icon',
            textContent: this.getStatusIcon(status)
        });

        const name = createElement('div', {
            className: 'health-name',
            textContent: serviceName
        });

        header.appendChild(icon);
        header.appendChild(name);
        card.appendChild(header);

        // Status text
        const statusText = createElement('div', {
            className: 'health-status',
            textContent: capitalize(status)
        });
        card.appendChild(statusText);

        // Metadata
        if (metadata.version) {
            const versionDiv = createElement('div', {
                style: 'font-size: 0.875rem; color: var(--gray-600); margin-top: var(--spacing-xs);',
                textContent: `Version: ${metadata.version}`
            });
            card.appendChild(versionDiv);
        }

        return card;
    }

    getStatusIcon(status) {
        const icons = {
            healthy: '✓',
            degraded: '⚠',
            unhealthy: '✗',
            unavailable: '✗'
        };

        return icons[status] || '?';
    }

    formatServiceName(serviceName) {
        // Convert "inference_service" to "Inference Service"
        return serviceName
            .split('_')
            .map(word => capitalize(word))
            .join(' ');
    }

    showError(error) {
        if (!this.container) return;

        clearElement(this.container);

        const errorCard = createElement('div', {
            className: 'health-card unhealthy'
        });

        const title = createElement('h3', {
            textContent: 'Health Check Failed',
            style: 'color: var(--error); margin-bottom: var(--spacing-sm);'
        });

        const message = createElement('p', {
            textContent: error.message || 'Unable to fetch health status',
            style: 'color: var(--gray-700);'
        });

        errorCard.appendChild(title);
        errorCard.appendChild(message);

        this.container.appendChild(errorCard);
    }

    updateLastUpdated() {
        const lastUpdatedElement = $('last-updated');
        if (lastUpdatedElement) {
            const now = new Date();
            lastUpdatedElement.textContent = now.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            lastUpdatedElement.dateTime = now.toISOString();
        }
    }

    updateAPIStatus(status) {
        const apiStatus = $('api-status');
        if (!apiStatus) return;

        const statusDot = apiStatus.querySelector('.status-dot');
        const statusText = apiStatus.querySelector('.status-text');

        if (statusDot) {
            statusDot.className = 'status-dot';
            if (status === 'connected') {
                statusDot.classList.add('connected');
            } else if (status === 'error') {
                statusDot.classList.add('error');
            }
        }

        if (statusText) {
            statusText.textContent = status === 'connected' ? 'API Connected' : 'API Error';
        }
    }

    startPolling() {
        if (!this.isAutoRefreshEnabled) return;

        // Poll every 10 seconds
        this.pollingInterval = setInterval(() => {
            this.loadHealth();
        }, 10000);

        // Update status indicator
        if (this.autoRefreshStatus) {
            this.autoRefreshStatus.textContent = 'Enabled';
        }
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }

        if (this.autoRefreshStatus) {
            this.autoRefreshStatus.textContent = 'Disabled';
        }
    }

    toggleAutoRefresh() {
        this.isAutoRefreshEnabled = !this.isAutoRefreshEnabled;

        if (this.isAutoRefreshEnabled) {
            this.startPolling();
        } else {
            this.stopPolling();
        }
    }

    destroy() {
        this.stopPolling();
    }
}
