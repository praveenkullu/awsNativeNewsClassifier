/**
 * Training Component
 * Handles model training jobs and version management
 */
class TrainingComponent {
    constructor(apiClient) {
        this.api = apiClient;
        this.form = $('training-form');
        this.jobsContainer = $('training-jobs');
        this.versionsContainer = $('model-versions');
        this.submitBtn = $('training-btn');
        this.activeJobs = new Map();
        this.pollingInterval = null;

        this.init();
    }

    async init() {
        if (!this.form) return;

        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });

        // Load initial data
        await this.loadModelVersions();

        // Start polling for active jobs (every 10 seconds)
        this.startPolling();
    }

    async handleSubmit() {
        // Get form values
        const modelType = $('model-type') ? $('model-type').value : 'logistic_regression';
        const includeFeedback = $('include-feedback') ? $('include-feedback').checked : true;
        const description = $('training-description') ? $('training-description').value.trim() : '';

        // Prepare config
        const config = {
            include_feedback: includeFeedback
        };

        if (description) {
            config.description = description;
        }

        // Add model type to config
        config.config = {
            model_type: modelType
        };

        // Show loading state
        this.setLoading(true);

        try {
            // Start training
            const result = await this.api.startTraining(config);

            // Show success
            showSuccess(`Training job started: ${result.training_job_id}`);

            // Reset form
            this.form.reset();

            // Add to active jobs
            this.activeJobs.set(result.training_job_id, {
                status: 'queued',
                progress: 0
            });

            // Refresh jobs display
            await this.loadActiveJobs();

        } catch (error) {
            console.error('Training start error:', error);
            showError(error.message || 'Failed to start training');
        } finally {
            this.setLoading(false);
        }
    }

    setLoading(loading) {
        if (this.submitBtn) {
            this.submitBtn.disabled = loading;
        }
    }

    async loadActiveJobs() {
        if (!this.jobsContainer) return;

        // For now, we'll just display jobs we've started
        // In a production app, you'd fetch all active jobs from the API
        if (this.activeJobs.size === 0) {
            clearElement(this.jobsContainer);
            const emptyState = createElement('div', {
                className: 'empty-state',
                textContent: 'No active training jobs'
            });
            this.jobsContainer.appendChild(emptyState);
            return;
        }

        clearElement(this.jobsContainer);

        // Poll each active job for status
        for (const [jobId, jobInfo] of this.activeJobs.entries()) {
            try {
                const status = await this.api.getTrainingStatus(jobId);
                this.activeJobs.set(jobId, status);

                // Display job card
                const jobCard = this.createJobCard(status);
                this.jobsContainer.appendChild(jobCard);

                // Remove from active jobs if completed or failed
                if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
                    setTimeout(() => {
                        this.activeJobs.delete(jobId);
                        this.loadActiveJobs();
                        this.loadModelVersions();
                    }, 5000); // Remove after 5 seconds
                }

            } catch (error) {
                console.error(`Failed to load job status for ${jobId}:`, error);
            }
        }
    }

    createJobCard(job) {
        const card = createElement('div', { className: 'job-card' });

        // Header
        const header = createElement('div', { className: 'job-header' });

        const jobId = createElement('span', {
            className: 'job-id',
            textContent: job.training_job_id || job.job_id || 'Unknown'
        });

        const statusBadge = createElement('span', {
            className: `status-badge ${job.status}`,
            textContent: job.status
        });

        header.appendChild(jobId);
        header.appendChild(statusBadge);
        card.appendChild(header);

        // Progress bar (if running)
        if (job.status === 'running' && job.progress !== undefined) {
            const progressBar = createElement('div', { className: 'progress-bar' });
            const progressFill = createElement('div', { className: 'progress-fill' });
            progressFill.style.width = `${job.progress * 100}%`;
            progressBar.appendChild(progressFill);
            card.appendChild(progressBar);

            // Progress text
            const progressText = createElement('div', {
                style: 'text-align: center; font-size: 0.875rem; color: var(--gray-600); margin-top: var(--spacing-xs);',
                textContent: `${Math.round(job.progress * 100)}% complete`
            });
            card.appendChild(progressText);
        }

        // Metadata
        const meta = createElement('div', { className: 'job-meta' });

        if (job.started_at) {
            const startedSpan = createElement('span', {
                textContent: `Started: ${formatDate(job.started_at)}`
            });
            meta.appendChild(startedSpan);
        }

        if (job.current_epoch && job.total_epochs) {
            const epochSpan = createElement('span', {
                textContent: `Epoch: ${job.current_epoch}/${job.total_epochs}`
            });
            meta.appendChild(epochSpan);
        }

        if (job.metrics && job.metrics.current_accuracy) {
            const accuracySpan = createElement('span', {
                textContent: `Accuracy: ${formatPercentage(job.metrics.current_accuracy)}`
            });
            meta.appendChild(accuracySpan);
        }

        if (meta.children.length > 0) {
            card.appendChild(meta);
        }

        return card;
    }

    async loadModelVersions() {
        if (!this.versionsContainer) return;

        // Show loading
        clearElement(this.versionsContainer);
        const loadingDiv = createElement('div', {
            className: 'loading',
            textContent: 'Loading model versions'
        });
        this.versionsContainer.appendChild(loadingDiv);

        try {
            const data = await this.api.getModelVersions({ limit: 10 });

            if (!data.versions || data.versions.length === 0) {
                clearElement(this.versionsContainer);
                const emptyState = createElement('div', {
                    className: 'empty-state',
                    textContent: 'No model versions found'
                });
                this.versionsContainer.appendChild(emptyState);
                return;
            }

            this.displayModelVersions(data.versions);

        } catch (error) {
            console.error('Failed to load model versions:', error);

            clearElement(this.versionsContainer);
            const errorDiv = createElement('div', {
                className: 'empty-state',
                textContent: 'Failed to load model versions'
            });
            this.versionsContainer.appendChild(errorDiv);
        }
    }

    displayModelVersions(versions) {
        if (!this.versionsContainer) return;

        clearElement(this.versionsContainer);

        // Create table
        const table = createElement('table', { className: 'versions-table' });

        // Header
        const thead = createElement('thead');
        const headerRow = createElement('tr');

        ['Version', 'Status', 'Accuracy', 'F1 Score', 'Created', 'Actions'].forEach(header => {
            const th = createElement('th', { textContent: header });
            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Body
        const tbody = createElement('tbody');

        versions.forEach(version => {
            const row = createElement('tr');

            // Version
            const versionCell = createElement('td');
            const versionSpan = createElement('span', {
                className: 'version-id',
                textContent: version.version
            });
            versionCell.appendChild(versionSpan);

            if (version.is_production) {
                const badge = createElement('span', {
                    className: 'badge production',
                    textContent: 'Production',
                    style: 'margin-left: var(--spacing-xs);'
                });
                versionCell.appendChild(badge);
            }
            row.appendChild(versionCell);

            // Status
            const statusCell = createElement('td');
            const statusBadge = createElement('span', {
                className: `badge ${version.status === 'active' ? '' : 'archived'}`,
                textContent: capitalize(version.status || 'active')
            });
            statusCell.appendChild(statusBadge);
            row.appendChild(statusCell);

            // Accuracy
            const accuracyCell = createElement('td', {
                textContent: version.metrics?.accuracy ? formatMetric(version.metrics.accuracy) : '--'
            });
            row.appendChild(accuracyCell);

            // F1 Score
            const f1Cell = createElement('td', {
                textContent: version.metrics?.f1_score ? formatMetric(version.metrics.f1_score) : '--'
            });
            row.appendChild(f1Cell);

            // Created
            const createdCell = createElement('td', {
                textContent: formatDate(version.created_at)
            });
            row.appendChild(createdCell);

            // Actions
            const actionsCell = createElement('td');

            if (!version.is_production && version.status === 'active') {
                const deployBtn = createElement('button', {
                    className: 'btn-small',
                    textContent: 'Deploy'
                });

                deployBtn.addEventListener('click', async () => {
                    await this.deployVersion(version.version);
                });

                actionsCell.appendChild(deployBtn);
            } else {
                actionsCell.textContent = '--';
            }

            row.appendChild(actionsCell);

            tbody.appendChild(row);
        });

        table.appendChild(tbody);

        this.versionsContainer.appendChild(table);
    }

    async deployVersion(version) {
        if (!confirm(`Deploy version ${version} to production?`)) {
            return;
        }

        try {
            await this.api.deployModel(version);

            showSuccess(`Version ${version} deployed successfully!`);

            // Reload versions
            await this.loadModelVersions();

        } catch (error) {
            console.error('Deploy error:', error);
            showError(error.message || 'Failed to deploy model');
        }
    }

    startPolling() {
        // Poll every 5 seconds for active jobs
        this.pollingInterval = setInterval(() => {
            if (this.activeJobs.size > 0) {
                this.loadActiveJobs();
            }
        }, 5000);
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    destroy() {
        this.stopPolling();
    }
}
