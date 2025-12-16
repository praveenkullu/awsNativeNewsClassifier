/**
 * DOM Utility Functions
 */

/**
 * Create an element with attributes and children
 */
function createElement(tag, attrs = {}, children = []) {
    const element = document.createElement(tag);

    // Set attributes
    Object.entries(attrs).forEach(([key, value]) => {
        if (key === 'className') {
            element.className = value;
        } else if (key === 'textContent') {
            element.textContent = value;
        } else if (key.startsWith('on') && typeof value === 'function') {
            // Event listener
            element.addEventListener(key.substring(2).toLowerCase(), value);
        } else {
            element.setAttribute(key, value);
        }
    });

    // Add children
    if (typeof children === 'string') {
        element.textContent = children;
    } else if (Array.isArray(children)) {
        children.forEach(child => {
            if (typeof child === 'string') {
                element.appendChild(document.createTextNode(child));
            } else if (child instanceof Node) {
                element.appendChild(child);
            }
        });
    } else if (children instanceof Node) {
        element.appendChild(children);
    }

    return element;
}

/**
 * Clear all children from an element
 */
function clearElement(element) {
    while (element.firstChild) {
        element.removeChild(element.firstChild);
    }
}

/**
 * Toggle a class on an element
 */
function toggleClass(element, className, force) {
    if (force !== undefined) {
        element.classList.toggle(className, force);
    } else {
        element.classList.toggle(className);
    }
}

/**
 * Add a class to an element
 */
function addClass(element, className) {
    element.classList.add(className);
}

/**
 * Remove a class from an element
 */
function removeClass(element, className) {
    element.classList.remove(className);
}

/**
 * Check if element has a class
 */
function hasClass(element, className) {
    return element.classList.contains(className);
}

/**
 * Show an element
 */
function show(element) {
    element.classList.remove('hidden');
}

/**
 * Hide an element
 */
function hide(element) {
    element.classList.add('hidden');
}

/**
 * Toggle element visibility
 */
function toggleVisibility(element) {
    element.classList.toggle('hidden');
}

/**
 * Set element's text content safely (prevents XSS)
 */
function setTextContent(element, text) {
    element.textContent = text;
}

/**
 * Set element's HTML content (use with caution)
 */
function setHTML(element, html) {
    element.innerHTML = html;
}

/**
 * Get element by ID
 */
function $(id) {
    return document.getElementById(id);
}

/**
 * Query selector
 */
function $$(selector) {
    return document.querySelector(selector);
}

/**
 * Query selector all
 */
function $$$(selector) {
    return document.querySelectorAll(selector);
}
