/**
 * Axis Allocation — Main JavaScript
 * Plain vanilla JS, no frameworks
 */

(function() {
    'use strict';

    // Theme toggle
    function initThemeToggle() {
        const toggle = document.querySelector('.theme-toggle');
        if (!toggle) return;

        // Get saved preference or system preference
        function getPreferredTheme() {
            const saved = localStorage.getItem('theme');
            if (saved) return saved;
            return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }

        // Apply theme
        function setTheme(theme) {
            if (theme === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
            } else {
                document.documentElement.removeAttribute('data-theme');
            }
            localStorage.setItem('theme', theme);
        }

        // Set initial theme
        setTheme(getPreferredTheme());

        // Toggle on click
        toggle.addEventListener('click', function() {
            const current = document.documentElement.getAttribute('data-theme');
            setTheme(current === 'dark' ? 'light' : 'dark');
        });
    }

    // Mobile navigation toggle
    function initMobileNav() {
        const toggle = document.querySelector('.nav-toggle');
        const nav = document.querySelector('.nav');

        if (toggle && nav) {
            toggle.addEventListener('click', function() {
                nav.classList.toggle('active');
            });

            // Close nav when clicking outside
            document.addEventListener('click', function(e) {
                if (!toggle.contains(e.target) && !nav.contains(e.target)) {
                    nav.classList.remove('active');
                }
            });
        }
    }

    // Form validation
    function initFormValidation() {
        const form = document.getElementById('mandate-form');
        if (!form) return;

        form.addEventListener('submit', function(e) {
            e.preventDefault();

            // Check required acknowledgements
            const ack1 = document.getElementById('ack-payment');
            const ack2 = document.getElementById('ack-refund');
            const ack3 = document.getElementById('ack-terms');

            if (!ack1.checked || !ack2.checked || !ack3.checked) {
                alert('All acknowledgements are required.');
                return;
            }

            // Check at least one asset class selected
            const assetClasses = document.querySelectorAll('input[name="asset_class[]"]:checked');
            if (assetClasses.length === 0) {
                alert('Select at least one asset class.');
                return;
            }

            // Basic field validation
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(function(field) {
                if (!field.value.trim()) {
                    isValid = false;
                    field.style.borderColor = '#c0392b';
                } else {
                    field.style.borderColor = '';
                }
            });

            if (!isValid) {
                alert('Complete all required fields.');
                return;
            }

            // If validation passes, show confirmation
            showSubmissionConfirmation();
        });

        // Clear error styling on input
        const inputs = form.querySelectorAll('.form-input, .form-select, .form-textarea');
        inputs.forEach(function(input) {
            input.addEventListener('input', function() {
                this.style.borderColor = '';
            });
        });
    }

    // Submission confirmation
    function showSubmissionConfirmation() {
        const form = document.getElementById('mandate-form');
        const formContainer = form.parentElement;

        // Create confirmation message
        const confirmation = document.createElement('div');
        confirmation.className = 'card';
        confirmation.innerHTML = `
            <h2>Mandate Submitted</h2>
            <p>
                Your mandate and engagement deposit have been received.
            </p>
            <p>
                Submission does not constitute acceptance. Mandates are reviewed on a
                discretionary basis. You will receive written confirmation of acceptance
                or decline.
            </p>
            <p class="text-muted text-small mb-0">
                See Terms of Service for refund policy.
            </p>
        `;

        // Replace form with confirmation
        form.style.display = 'none';
        formContainer.appendChild(confirmation);

        // Scroll to confirmation
        confirmation.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Initialise on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        initThemeToggle();
        initMobileNav();
        initFormValidation();
    });

})();


/**
 * Stripe Integration Placeholder
 *
 * Payment is collected at submission. Integration options:
 *
 * Option A: Stripe Payment Links
 * - Create payment link in Stripe Dashboard for £500
 * - Redirect form submission to payment link
 * - Use Stripe webhooks for confirmation
 *
 * Option B: Stripe Checkout (requires backend)
 * - Create checkout session server-side
 * - Redirect to Stripe Checkout on form submit
 * - Handle webhooks for payment confirmation
 */
