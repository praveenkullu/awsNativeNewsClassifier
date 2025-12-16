/**
 * API Client for ML News Categorization API
 * Handles all HTTP requests to the backend
 */
class APIClient {
    constructor(baseURL = 'https://w6of479oic.execute-api.us-east-2.amazonaws.com/api/v1') {
        this.baseURL = baseURL;
        this.correlationId = null;
    }

    /**
     * Generic request method
     */
    async request(endpoint, options = {}) {
        // Handle different endpoint types:
        // - Absolute URLs (http/https) → use as-is
        // - Endpoints with /api/v1 already → use as-is
        // - Health endpoints (/health*) → use as-is (root level)
        // - Everything else → prepend baseURL (/api/v1)
        let url;
        if (endpoint.startsWith('http')) {
            url = endpoint;
        } else if (endpoint.includes('/api/v1')) {
            // Already has full path
            url = endpoint;
        } else if (endpoint.startsWith('/health')) {
            // Root-level health endpoint
            url = endpoint;
        } else {
            // API endpoint - prepend baseURL
            url = `${this.baseURL}${endpoint}`;
        }

        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        // Merge options
        const fetchOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };

        try {
            const response = await fetch(url, fetchOptions);

            // Get correlation ID from response headers
            this.correlationId = response.headers.get('X-Correlation-ID');

            // Parse JSON response
            let data;
            const contentType = response.headers.get('Content-Type');
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            // Handle errors
            if (!response.ok) {
                const error = new Error(data.error?.message || `HTTP ${response.status}: ${response.statusText}`);
                error.status = response.status;
                error.correlationId = this.correlationId;
                error.details = data.error?.details;
                throw error;
            }

            return data;
        } catch (error) {
            // Network errors
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                const networkError = new Error('Network error: Unable to reach the server');
                networkError.status = 0;
                networkError.isNetworkError = true;
                throw networkError;
            }
            throw error;
        }
    }

    /**
     * GET request
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;

        return this.request(url, {
            method: 'GET',
        });
    }

    /**
     * POST request
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * PUT request
     */
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE',
        });
    }

    // ==================== Inference Endpoints ====================

    /**
     * Predict category for a single article
     */
    async predict(data) {
        return this.post('/predict', data);
    }

    /**
     * Predict categories for multiple articles
     */
    async predictBatch(articles) {
        return this.post('/predict/batch', { articles });
    }

    // ==================== Feedback Endpoints ====================

    /**
     * Submit feedback on a prediction
     */
    async submitFeedback(data) {
        return this.post('/feedback', data);
    }

    /**
     * Get feedback statistics
     */
    async getFeedbackStats(params = {}) {
        return this.get('/feedback/stats', params);
    }

    /**
     * List feedback records
     */
    async listFeedback(params = {}) {
        return this.get('/feedback', params);
    }

    // ==================== Model Training Endpoints ====================

    /**
     * Start a training job
     */
    async startTraining(config) {
        return this.post('/model/train', config);
    }

    /**
     * Get training job status
     */
    async getTrainingStatus(jobId) {
        return this.get(`/model/train/${jobId}`);
    }

    /**
     * List model versions
     */
    async getModelVersions(params = {}) {
        return this.get('/model/versions', params);
    }

    /**
     * Deploy a model version
     */
    async deployModel(version) {
        return this.post(`/model/deploy/${version}`);
    }

    // ==================== Evaluation Endpoints ====================

    /**
     * Start model evaluation
     */
    async evaluateModel(data) {
        return this.post('/model/evaluate', data);
    }

    /**
     * Get evaluation results
     */
    async getEvaluationResult(evaluationId) {
        return this.get(`/model/evaluate/${evaluationId}`);
    }

    /**
     * Check if retraining is needed
     */
    async checkRetraining() {
        return this.post('/model/retrain-check');
    }

    // ==================== Health & Info Endpoints ====================

    /**
     * Get health status
     */
    async getHealth() {
        return this.get('https://w6of479oic.execute-api.us-east-2.amazonaws.com/health');
    }

    /**
     * Get API information
     */
    async getAPIInfo() {
        return this.get('/info');
    }

    /**
     * Get liveness status
     */
    async getLiveness() {
        return this.get('/health/live', {}, true);
    }

    /**
     * Get readiness status
     */
    async getReadiness() {
        return this.get('/health/ready', {}, true);
    }
}

// Create global API client instance
const api = new APIClient();
