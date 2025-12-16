/**
 * Feedback Component
 * Handles feedback submission and statistics display
 */
class FeedbackComponent {
    constructor(apiClient) {
        this.api = apiClient;
        this.form = $('feedback-form');
        this.statsContainer = $('feedback-stats');
        this.predictionIdInput = $('prediction-id');
        this.categorySelect = $('correct-category');
        this.submitBtn = $('feedback-btn');
        this.categories = [];

        this.init();
    }

    async init() {
        if (!this.form) return;

        // Load categories for dropdown
        await this.loadCategories();

        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });

        // Clear errors on input
        if (this.predictionIdInput) {
            this.predictionIdInput.addEventListener('input', () => {
                clearFieldError('prediction-id');
            });
        }

        // Load statistics
        this.loadStatistics();
    }

    async loadCategories() {
        try {
            const info = await this.api.getAPIInfo();

            if (info.categories && Array.isArray(info.categories)) {
                this.categories = info.categories;
                this.populateCategoryDropdown();
            }
        } catch (error) {
            console.error('Failed to load categories:', error);
            showError('Failed to load categories');
        }
    }

    populateCategoryDropdown() {
        if (!this.categorySelect) return;

        // Clear existing options (except the first placeholder)
        while (this.categorySelect.options.length > 1) {
            this.categorySelect.remove(1);
        }

        // Add category options
        this.categories.forEach(category => {
            const option = createElement('option', {
                value: category,
                textContent: category
            });
            this.categorySelect.appendChild(option);
        });
    }

    async handleSubmit() {
        // Get form values
        const predictionId = this.predictionIdInput ? this.predictionIdInput.value.trim() : '';
        const correctCategory = this.categorySelect ? this.categorySelect.value : '';
        const feedbackType = this.form.querySelector('input[name="feedback_type"]:checked')?.value || 'correction';
        const comment = $('comment') ? $('comment').value.trim() : '';

        // Clear previous errors
        clearFormErrors('feedback-form');

        // Validate prediction ID
        const predIdValidation = validatePredictionId(predictionId);
        if (!predIdValidation.valid) {
            showFieldError('prediction-id', predIdValidation.error);
            showError(predIdValidation.error);
            return;
        }

        // Validate category selection
        if (!correctCategory) {
            showError('Please select a category');
            return;
        }

        // Prepare data
        const data = {
            prediction_id: predictionId,
            correct_category: correctCategory,
            feedback_type: feedbackType
        };

        if (comment) {
            data.comment = comment;
        }

        // Show loading state
        this.setLoading(true);

        try {
            // Submit feedback
            const result = await this.api.submitFeedback(data);

            // Show success
            showSuccess('Feedback submitted successfully!');

            // Reset form
            this.form.reset();

            // Reload statistics
            await this.loadStatistics();

        } catch (error) {
            console.error('Feedback submission error:', error);
            showError(error.message || 'Failed to submit feedback');
        } finally {
            this.setLoading(false);
        }
    }

    setLoading(loading) {
        if (this.submitBtn) {
            this.submitBtn.disabled = loading;
        }
    }

    async loadStatistics() {
        if (!this.statsContainer) return;

        // Show loading
        clearElement(this.statsContainer);
        const loadingDiv = createElement('div', {
            className: 'loading',
            textContent: 'Loading statistics'
        });
        this.statsContainer.appendChild(loadingDiv);

        try {
            const stats = await this.api.getFeedbackStats();

            this.displayStatistics(stats);

        } catch (error) {
            console.error('Failed to load statistics:', error);

            clearElement(this.statsContainer);
            const errorDiv = createElement('div', {
                className: 'empty-state',
                textContent: 'Failed to load statistics'
            });
            this.statsContainer.appendChild(errorDiv);
        }
    }

    displayStatistics(stats) {
        if (!this.statsContainer) return;

        clearElement(this.statsContainer);

        // Create stats grid
        const statsGrid = createElement('div', { className: 'stats-container' });

        // Total predictions
        const totalPredCard = this.createStatCard(
            formatNumber(stats.total_predictions || 0),
            'Total Predictions'
        );
        statsGrid.appendChild(totalPredCard);

        // Total feedback
        const totalFeedbackCard = this.createStatCard(
            formatNumber(stats.total_feedback || 0),
            'Total Feedback'
        );
        statsGrid.appendChild(totalFeedbackCard);

        // Feedback rate
        const feedbackRateCard = this.createStatCard(
            formatPercentage(stats.feedback_rate || 0),
            'Feedback Rate'
        );
        statsGrid.appendChild(feedbackRateCard);

        // Accuracy from feedback
        const accuracyCard = this.createStatCard(
            formatPercentage(stats.accuracy_from_feedback || 0),
            'Accuracy from Feedback'
        );
        statsGrid.appendChild(accuracyCard);

        this.statsContainer.appendChild(statsGrid);

        // Corrections by category table
        if (stats.corrections_by_category && Object.keys(stats.corrections_by_category).length > 0) {
            const tableTitle = createElement('h3', {
                textContent: 'Corrections by Category',
                style: 'margin-top: var(--spacing-xl); margin-bottom: var(--spacing-md);'
            });
            this.statsContainer.appendChild(tableTitle);

            const table = this.createCorrectionsTable(stats.corrections_by_category);
            this.statsContainer.appendChild(table);
        }
    }

    createStatCard(value, label) {
        const card = createElement('div', { className: 'stat-card' });

        const valueSpan = createElement('span', {
            className: 'stat-value',
            textContent: value
        });

        const labelSpan = createElement('span', {
            className: 'stat-label',
            textContent: label
        });

        card.appendChild(valueSpan);
        card.appendChild(labelSpan);

        return card;
    }

    createCorrectionsTable(corrections) {
        const table = createElement('table', { className: 'stats-table' });

        // Header
        const thead = createElement('thead');
        const headerRow = createElement('tr');

        const categoryHeader = createElement('th', { textContent: 'Category' });
        const correctionsHeader = createElement('th', { textContent: 'Corrections' });

        headerRow.appendChild(categoryHeader);
        headerRow.appendChild(correctionsHeader);
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Body
        const tbody = createElement('tbody');

        // Sort by corrections count (descending)
        const sortedCategories = Object.entries(corrections)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10); // Top 10

        sortedCategories.forEach(([category, count]) => {
            const row = createElement('tr');

            const categoryCell = createElement('td', { textContent: category });
            const countCell = createElement('td', { textContent: formatNumber(count) });

            row.appendChild(categoryCell);
            row.appendChild(countCell);
            tbody.appendChild(row);
        });

        table.appendChild(tbody);

        return table;
    }

    prefillPredictionId(predictionId) {
        if (this.predictionIdInput) {
            this.predictionIdInput.value = predictionId;
            this.predictionIdInput.focus();

            // Scroll to form
            this.form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
}
