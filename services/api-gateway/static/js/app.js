/**
 * Main Application
 * Initializes and coordinates all components
 */
class App {
    constructor() {
        this.api = api; // Global API client from api.js
        this.currentTab = 'predict';
        this.components = {};
        this.apiInfo = null;
    }

    async init() {
        console.log('Initializing ML News Categorization Dashboard...');

        // Setup tab navigation
        this.setupTabs();

        // Initialize components
        this.components.prediction = new PredictionComponent(this.api);
        this.components.feedback = new FeedbackComponent(this.api);
        this.components.training = new TrainingComponent(this.api);
        this.components.health = new HealthComponent(this.api);

        // Store feedback component globally for cross-component access
        window.feedbackComponent = this.components.feedback;

        // Load API info
        await this.loadAPIInfo();

        // Setup info button
        this.setupInfoButton();

        // Log initialization complete
        console.log('Dashboard initialized successfully');

        // Show welcome notification
        showInfo('Welcome to ML News Categorization Dashboard', 3000);
    }

    setupTabs() {
        const tabs = document.querySelectorAll('.tab');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                this.switchTab(tabName);
            });
        });
    }

    switchTab(tabName) {
        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });

        // Remove active from all tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.remove('active');
            tab.setAttribute('aria-selected', 'false');
        });

        // Show selected tab
        const selectedTabContent = $(`${tabName}-tab`);
        if (selectedTabContent) {
            selectedTabContent.classList.add('active');
        }

        // Activate tab button
        const selectedTab = document.querySelector(`[data-tab="${tabName}"]`);
        if (selectedTab) {
            selectedTab.classList.add('active');
            selectedTab.setAttribute('aria-selected', 'true');
        }

        this.currentTab = tabName;

        console.log(`Switched to ${tabName} tab`);
    }

    async loadAPIInfo() {
        try {
            this.apiInfo = await this.api.getAPIInfo();
            console.log('API Info loaded:', this.apiInfo);
        } catch (error) {
            console.error('Failed to load API info:', error);
            showError('Failed to load API information');
        }
    }

    setupInfoButton() {
        const infoBtn = $('info-btn');
        if (!infoBtn) return;

        infoBtn.addEventListener('click', () => {
            this.showAPIInfoModal();
        });
    }

    showAPIInfoModal() {
        if (!this.apiInfo) {
            showWarning('API information not available');
            return;
        }

        // Create a simple modal using notification
        const message = `
${this.apiInfo.name} v${this.apiInfo.version}

${this.apiInfo.description}

${Object.keys(this.apiInfo.endpoints).length} API endpoints available
${this.apiInfo.categories.length} news categories
        `.trim();

        showInfo(message, 8000);
    }

    getCurrentTab() {
        return this.currentTab;
    }

    getComponent(name) {
        return this.components[name];
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Create global app instance
    window.app = new App();

    // Initialize
    window.app.init().catch(error => {
        console.error('Failed to initialize app:', error);
        showError('Failed to initialize application');
    });
});

// Handle page visibility change (pause/resume polling)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('Page hidden - pausing background tasks');
        // Components handle their own polling, no action needed
    } else {
        console.log('Page visible - resuming background tasks');
        // Refresh health status when page becomes visible
        if (window.app && window.app.components.health) {
            window.app.components.health.loadHealth();
        }
    }
});

// Handle errors globally
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
});
