/**
 * K-Laboratory Website JavaScript
 * Version: 2.0 (Modernized)
 *
 * Improvements:
 * - ES6+ syntax
 * - Strict mode
 * - No global variable pollution
 * - Proper error handling
 * - Accessibility support
 */

'use strict';

/**
 * Popup window utility module
 * @namespace KLab
 */
const KLab = (function() {

    /**
     * Opens a popup window with specified options
     * @param {Object} config - Configuration object
     * @param {string} config.url - URL to open
     * @param {number} config.width - Window width in pixels
     * @param {number} config.height - Window height in pixels
     * @param {boolean} [config.showTools=false] - Show browser toolbar
     * @param {string} [config.name=''] - Window name
     * @returns {Window|null} Reference to popup window or null if blocked
     */
    function openPopup(config) {
        const {
            url,
            width,
            height,
            showTools = false,
            name = ''
        } = config;

        // Validate required parameters
        if (!url || !width || !height) {
            console.error('KLab.openPopup: Missing required parameters (url, width, height)');
            return null;
        }

        // Validate URL
        if (!isValidUrl(url)) {
            console.error('KLab.openPopup: Invalid URL provided');
            return null;
        }

        // Build options string
        let options = `width=${width},height=${height}`;

        if (!showTools) {
            options += ',menubar=no,toolbar=no,status=no,resizable=no,scrollbars=no,location=no';
        }

        // Open popup
        const popupWindow = window.open(url, name, options);

        // Check if popup was blocked
        if (!popupWindow || popupWindow.closed || typeof popupWindow.closed === 'undefined') {
            console.warn('KLab.openPopup: Popup was blocked by browser');
            return null;
        }

        // Focus the popup
        popupWindow.focus();

        return popupWindow;
    }

    /**
     * Legacy function for backwards compatibility
     * @deprecated Use KLab.openPopup() instead
     */
    function commonPopup(url, width, height, toolsInd, name) {
        console.warn('commonPopup is deprecated. Use KLab.openPopup() instead.');

        return openPopup({
            url: url,
            width: width,
            height: height,
            showTools: toolsInd !== 1,
            name: name || ''
        });
    }

    /**
     * Validates a URL string
     * @param {string} url - URL to validate
     * @returns {boolean} True if valid
     */
    function isValidUrl(url) {
        try {
            new URL(url, window.location.origin);
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Smooth scroll to element
     * @param {string} selector - CSS selector for target element
     */
    function scrollToElement(selector) {
        const element = document.querySelector(selector);
        if (element) {
            element.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    }

    /**
     * Initialize navigation accessibility
     */
    function initAccessibility() {
        // Add keyboard navigation support
        document.addEventListener('keydown', function(e) {
            // Skip to main content with Enter on skip link
            if (e.key === 'Enter' && e.target.classList.contains('skip-link')) {
                e.preventDefault();
                const main = document.querySelector('main');
                if (main) {
                    main.tabIndex = -1;
                    main.focus();
                }
            }
        });

        // Enhance focus visibility
        document.body.addEventListener('mousedown', function() {
            document.body.classList.add('using-mouse');
        });

        document.body.addEventListener('keydown', function(e) {
            if (e.key === 'Tab') {
                document.body.classList.remove('using-mouse');
            }
        });
    }

    /**
     * Initialize lazy loading for images
     */
    function initLazyLoading() {
        // Check for native lazy loading support
        if ('loading' in HTMLImageElement.prototype) {
            // Browser supports native lazy loading
            const images = document.querySelectorAll('img[loading="lazy"]');
            images.forEach(function(img) {
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                }
            });
        } else {
            // Fallback for older browsers
            const lazyImages = document.querySelectorAll('img[data-src]');

            if ('IntersectionObserver' in window) {
                const imageObserver = new IntersectionObserver(function(entries) {
                    entries.forEach(function(entry) {
                        if (entry.isIntersecting) {
                            const img = entry.target;
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                            imageObserver.unobserve(img);
                        }
                    });
                });

                lazyImages.forEach(function(img) {
                    imageObserver.observe(img);
                });
            } else {
                // Final fallback - load all images
                lazyImages.forEach(function(img) {
                    img.src = img.dataset.src;
                });
            }
        }
    }

    /**
     * Initialize all modules when DOM is ready
     */
    function init() {
        initAccessibility();
        initLazyLoading();
        console.log('K-Laboratory scripts initialized');
    }

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    return {
        openPopup: openPopup,
        commonPopup: commonPopup, // Legacy support
        scrollToElement: scrollToElement,
        init: init
    };

})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = KLab;
}
