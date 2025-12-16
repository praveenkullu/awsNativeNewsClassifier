/**
 * Form Validation Utilities
 */

/**
 * Validate headline
 */
function validateHeadline(text) {
    if (!text || text.trim().length === 0) {
        return {
            valid: false,
            error: 'Headline is required'
        };
    }

    if (text.length > 500) {
        return {
            valid: false,
            error: 'Headline must be less than 500 characters'
        };
    }

    return { valid: true };
}

/**
 * Validate description
 */
function validateDescription(text) {
    if (!text) {
        return { valid: true }; // Optional field
    }

    if (text.length > 2000) {
        return {
            valid: false,
            error: 'Description must be less than 2000 characters'
        };
    }

    return { valid: true };
}

/**
 * Validate prediction ID format
 */
function validatePredictionId(id) {
    if (!id || id.trim().length === 0) {
        return {
            valid: false,
            error: 'Prediction ID is required'
        };
    }

    // Basic format check - should start with "pred_"
    if (!id.startsWith('pred_')) {
        return {
            valid: false,
            error: 'Invalid prediction ID format (should start with "pred_")'
        };
    }

    return { valid: true };
}

/**
 * Validate training configuration
 */
function validateTrainingConfig(config) {
    const errors = {};

    // Validate epochs (if provided)
    if (config.epochs !== undefined) {
        const epochs = parseInt(config.epochs);
        if (isNaN(epochs) || epochs < 1 || epochs > 100) {
            errors.epochs = 'Epochs must be between 1 and 100';
        }
    }

    // Validate batch size (if provided)
    if (config.batch_size !== undefined) {
        const batchSize = parseInt(config.batch_size);
        if (isNaN(batchSize) || batchSize < 8 || batchSize > 256) {
            errors.batch_size = 'Batch size must be between 8 and 256';
        }
    }

    // Validate learning rate (if provided)
    if (config.learning_rate !== undefined) {
        const lr = parseFloat(config.learning_rate);
        if (isNaN(lr) || lr <= 0 || lr >= 1) {
            errors.learning_rate = 'Learning rate must be between 0 and 1 (exclusive)';
        }
    }

    // Validate max features (if provided)
    if (config.max_features !== undefined) {
        const maxFeatures = parseInt(config.max_features);
        if (isNaN(maxFeatures) || maxFeatures < 1000 || maxFeatures > 20000) {
            errors.max_features = 'Max features must be between 1000 and 20000';
        }
    }

    return {
        valid: Object.keys(errors).length === 0,
        errors
    };
}

/**
 * Validate email (if needed for future features)
 */
function validateEmail(email) {
    if (!email || email.trim().length === 0) {
        return {
            valid: false,
            error: 'Email is required'
        };
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        return {
            valid: false,
            error: 'Invalid email format'
        };
    }

    return { valid: true };
}

/**
 * Show validation error on form field
 */
function showFieldError(fieldId, message) {
    const field = document.getElementById(fieldId);
    const errorElement = document.getElementById(`${fieldId}-error`);

    if (field) {
        field.classList.add('error');
    }

    if (errorElement) {
        errorElement.textContent = message;
        errorElement.classList.add('show');
    }
}

/**
 * Clear validation error from form field
 */
function clearFieldError(fieldId) {
    const field = document.getElementById(fieldId);
    const errorElement = document.getElementById(`${fieldId}-error`);

    if (field) {
        field.classList.remove('error');
    }

    if (errorElement) {
        errorElement.textContent = '';
        errorElement.classList.remove('show');
    }
}

/**
 * Clear all validation errors from a form
 */
function clearFormErrors(formId) {
    const form = document.getElementById(formId);
    if (!form) return;

    // Clear all error classes from inputs
    const inputs = form.querySelectorAll('.error');
    inputs.forEach(input => input.classList.remove('error'));

    // Clear all error messages
    const errorMessages = form.querySelectorAll('.error-message');
    errorMessages.forEach(msg => {
        msg.textContent = '';
        msg.classList.remove('show');
    });
}

/**
 * Validate required field
 */
function validateRequired(value, fieldName = 'This field') {
    if (value === null || value === undefined || value.toString().trim().length === 0) {
        return {
            valid: false,
            error: `${fieldName} is required`
        };
    }

    return { valid: true };
}

/**
 * Validate number range
 */
function validateRange(value, min, max, fieldName = 'Value') {
    const num = parseFloat(value);

    if (isNaN(num)) {
        return {
            valid: false,
            error: `${fieldName} must be a number`
        };
    }

    if (num < min || num > max) {
        return {
            valid: false,
            error: `${fieldName} must be between ${min} and ${max}`
        };
    }

    return { valid: true };
}

/**
 * Validate string length
 */
function validateLength(value, min, max, fieldName = 'This field') {
    const length = value ? value.length : 0;

    if (min !== null && length < min) {
        return {
            valid: false,
            error: `${fieldName} must be at least ${min} characters`
        };
    }

    if (max !== null && length > max) {
        return {
            valid: false,
            error: `${fieldName} must be less than ${max} characters`
        };
    }

    return { valid: true };
}
