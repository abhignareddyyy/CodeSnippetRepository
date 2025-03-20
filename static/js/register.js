class RegisterManager {
    constructor() {
        this.form = document.getElementById('register-form');
        this.init();
    }

    init() {
        this.setupFormSubmission();
        this.setupInputAnimations();
    }

    setupFormSubmission() {
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitButton = this.form.querySelector('button[type="submit"]');
            this.setLoadingState(submitButton, true);

            try {
                const formData = new FormData(this.form);
                const response = await fetch(this.form.action, {
                    method: 'POST',
                    body: formData
                });

                if (response.redirected) {
                    // Handle Flask redirect (302) on success
                    this.showSuccess('Registration successful! Redirecting...');
                    setTimeout(() => window.location.href = response.url, 1000);
                } else if (!response.ok) {
                    // Handle non-redirect errors (e.g., 500)
                    throw new Error(`Server error: ${response.status}`);
                } else {
                    // Handle 200 response with HTML (e.g., duplicate error)
                    const html = await response.text();
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const flashMessages = doc.querySelectorAll('.bg-red-900\\/50, .bg-green-900\\/50');
                    if (flashMessages.length > 0) {
                        flashMessages.forEach(msg => {
                            this.showToast(msg.textContent.trim(), msg.classList.contains('bg-red-900\\/50') ? 'error' : 'success');
                        });
                    } else {
                        this.showError('Unexpected response from server');
                    }
                }
            } catch (error) {
                console.error('Registration error:', error);
                this.showError(`Registration failed: ${error.message}`);
            } finally {
                this.setLoadingState(submitButton, false);
            }
        });
    }

    setupInputAnimations() {
        const inputs = document.querySelectorAll('input');
        inputs.forEach(input => {
            const label = input.previousElementSibling;

            input.addEventListener('focus', () => {
                label.classList.add('-translate-y-2', 'scale-75', 'text-accent');
                input.parentElement.classList.add('scale-[1.02]');
            });

            input.addEventListener('blur', () => {
                if (!input.value) {
                    label.classList.remove('-translate-y-2', 'scale-75', 'text-accent');
                }
                input.parentElement.classList.remove('scale-[1.02]');
            });

            if (input.value) {
                label.classList.add('-translate-y-2', 'scale-75');
            }
        });
    }

    setLoadingState(button, isLoading) {
        if (isLoading) {
            button.disabled = true;
            button.innerHTML = `
                <svg class="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Creating account...
            `;
        } else {
            button.disabled = false;
            button.innerHTML = 'Register';
        }
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg animate-fade-in z-50
            ${type === 'success' ? 'bg-accent text-white' : 'bg-red-500 text-white'}`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.remove('animate-fade-in');
            toast.classList.add('animate-fade-out');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new RegisterManager();
});