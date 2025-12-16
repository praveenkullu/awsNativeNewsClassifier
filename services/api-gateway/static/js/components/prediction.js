/**
 * Prediction Component
 * Handles news article prediction form and results
 */
class PredictionComponent {
    constructor(apiClient) {
        this.api = apiClient;
        this.form = $('prediction-form');
        this.resultContainer = $('prediction-result');
        this.headlineInput = $('headline');
        this.descriptionInput = $('description');
        this.submitBtn = $('predict-btn');
        this.lastPredictionId = null;

        this.init();
    }

    init() {
        if (!this.form) return;

        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });

        // Character counters
        if (this.headlineInput) {
            this.headlineInput.addEventListener('input', () => {
                this.updateCharCount('headline', this.headlineInput.value.length, 500);
            });
        }

        if (this.descriptionInput) {
            this.descriptionInput.addEventListener('input', () => {
                this.updateCharCount('description', this.descriptionInput.value.length, 2000);
            });
        }

        // Clear errors on input
        [this.headlineInput, this.descriptionInput].forEach(input => {
            if (input) {
                input.addEventListener('input', () => {
                    clearFieldError(input.id);
                });
            }
        });
    }

    updateCharCount(fieldName, count, max) {
        const countElement = $(`${fieldName}-count`);
        if (countElement) {
            countElement.textContent = count;

            // Change color if near limit
            const parent = countElement.parentElement;
            if (count > max * 0.9) {
                parent.style.color = 'var(--warning)';
            } else if (count > max * 0.95) {
                parent.style.color = 'var(--error)';
            } else {
                parent.style.color = '';
            }
        }
    }

    async handleSubmit() {
        // Get form values
        const headline = this.headlineInput ? this.headlineInput.value.trim() : '';
        const description = this.descriptionInput ? this.descriptionInput.value.trim() : '';

        // Clear previous errors
        clearFormErrors('prediction-form');

        // Validate
        const headlineValidation = validateHeadline(headline);
        if (!headlineValidation.valid) {
            showFieldError('headline', headlineValidation.error);
            showError(headlineValidation.error);
            return;
        }

        const descValidation = validateDescription(description);
        if (!descValidation.valid) {
            showFieldError('description', descValidation.error);
            showError(descValidation.error);
            return;
        }

        // Prepare data
        const data = { headline };
        if (description) {
            data.short_description = description;
        }

        // Show loading state
        this.setLoading(true);
        this.showLoadingResult();

        try {
            // Make API call
            const result = await this.api.predict(data);

            // Store prediction ID
            this.lastPredictionId = result.prediction_id;

            // Display result
            this.displayResult(result);

            // Show success notification
            showSuccess('Prediction completed successfully!');

        } catch (error) {
            console.error('Prediction error:', error);

            // Show error
            this.showError(error);

            // Show error notification
            const errorMessage = error.message || 'Failed to get prediction';
            showError(errorMessage);

        } finally {
            this.setLoading(false);
        }
    }

    setLoading(loading) {
        if (this.submitBtn) {
            this.submitBtn.disabled = loading;
        }
    }

    showLoadingResult() {
        if (!this.resultContainer) return;

        clearElement(this.resultContainer);

        const loadingDiv = createElement('div', {
            className: 'loading',
            textContent: 'Analyzing your headline'
        });

        this.resultContainer.appendChild(loadingDiv);
    }

    displayResult(result) {
        if (!this.resultContainer) return;

        clearElement(this.resultContainer);

        // Create result card
        const resultCard = createElement('div', { className: 'prediction-result' });

        // Title
        const title = createElement('h3', { textContent: 'Prediction Result' });
        resultCard.appendChild(title);

        // Main prediction
        const mainPrediction = createElement('div', { className: 'main-prediction' });

        const categorySpan = createElement('span', {
            className: 'category',
            textContent: result.category
        });

        const confidenceSpan = createElement('span', {
            className: 'confidence',
            textContent: formatPercentage(result.confidence, 1)
        });

        mainPrediction.appendChild(categorySpan);
        mainPrediction.appendChild(confidenceSpan);
        resultCard.appendChild(mainPrediction);

        // Top predictions
        if (result.top_categories && result.top_categories.length > 0) {
            const topPredictions = createElement('div', { className: 'top-predictions' });

            const topTitle = createElement('h4', { textContent: 'Top 3 Categories:' });
            topPredictions.appendChild(topTitle);

            // Take top 3
            const top3 = result.top_categories.slice(0, 3);

            top3.forEach(cat => {
                const item = createElement('div', { className: 'prediction-item' });

                const categoryName = createElement('span', {
                    className: 'category-name',
                    textContent: cat.category
                });

                const bar = createElement('div', { className: 'confidence-bar' });
                const fill = createElement('div', {
                    className: 'confidence-fill'
                });
                fill.style.width = `${cat.confidence * 100}%`;
                bar.appendChild(fill);

                const value = createElement('span', {
                    className: 'confidence-value',
                    textContent: formatPercentage(cat.confidence, 1)
                });

                item.appendChild(categoryName);
                item.appendChild(bar);
                item.appendChild(value);

                topPredictions.appendChild(item);
            });

            resultCard.appendChild(topPredictions);
        }

        // Metadata
        const meta = createElement('div', { className: 'prediction-meta' });

        const predIdP = createElement('p');
        const predIdStrong = createElement('strong', { textContent: 'Prediction ID: ' });
        const predIdCode = createElement('code', { textContent: result.prediction_id });
        predIdP.appendChild(predIdStrong);
        predIdP.appendChild(predIdCode);
        meta.appendChild(predIdP);

        const modelVersionP = createElement('p');
        const modelVersionStrong = createElement('strong', { textContent: 'Model Version: ' });
        const modelVersionText = document.createTextNode(result.model_version || 'N/A');
        modelVersionP.appendChild(modelVersionStrong);
        modelVersionP.appendChild(modelVersionText);
        meta.appendChild(modelVersionP);

        const processingTimeP = createElement('p');
        const processingTimeStrong = createElement('strong', { textContent: 'Processing Time: ' });
        const processingTimeText = document.createTextNode(formatDuration(result.processing_time_ms));
        processingTimeP.appendChild(processingTimeStrong);
        processingTimeP.appendChild(processingTimeText);
        meta.appendChild(processingTimeP);

        resultCard.appendChild(meta);

        // Feedback button
        const feedbackBtn = createElement('button', {
            className: 'btn-secondary mt-lg',
            textContent: 'Submit Feedback on This Prediction'
        });

        feedbackBtn.addEventListener('click', () => {
            this.switchToFeedbackTab(result.prediction_id);
        });

        resultCard.appendChild(feedbackBtn);

        // Add to container
        this.resultContainer.appendChild(resultCard);
    }

    showError(error) {
        if (!this.resultContainer) return;

        clearElement(this.resultContainer);

        const errorDiv = createElement('div', {
            className: 'prediction-result',
            style: 'border-left: 4px solid var(--error);'
        });

        const errorTitle = createElement('h3', {
            textContent: 'Prediction Failed',
            style: 'color: var(--error);'
        });

        const errorMessage = createElement('p', {
            textContent: error.message || 'An unexpected error occurred',
            style: 'color: var(--gray-700); margin-top: var(--spacing-sm);'
        });

        errorDiv.appendChild(errorTitle);
        errorDiv.appendChild(errorMessage);

        if (error.correlationId) {
            const correlationP = createElement('p', {
                style: 'font-size: 0.875rem; color: var(--gray-600); margin-top: var(--spacing-sm);'
            });
            const correlationStrong = createElement('strong', { textContent: 'Correlation ID: ' });
            const correlationCode = createElement('code', { textContent: error.correlationId });
            correlationP.appendChild(correlationStrong);
            correlationP.appendChild(correlationCode);
            errorDiv.appendChild(correlationP);
        }

        this.resultContainer.appendChild(errorDiv);
    }

    switchToFeedbackTab(predictionId) {
        // Switch to feedback tab
        const feedbackTab = $$('[data-tab="feedback"]');
        if (feedbackTab) {
            feedbackTab.click();
        }

        // Prefill prediction ID
        if (window.feedbackComponent) {
            window.feedbackComponent.prefillPredictionId(predictionId);
        }
    }

    getPredictionId() {
        return this.lastPredictionId;
    }
}
