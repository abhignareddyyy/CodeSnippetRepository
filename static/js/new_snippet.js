class SnippetEditor {
    constructor() {
        this.form = document.getElementById('snippet-form');
        this.previewModal = document.getElementById('preview-modal');
        this.codeTextarea = document.getElementById('code'); // Hidden textarea
        this.codeEditor = null; // Will hold CodeMirror instance
        this.init();
    }

    init() {
        if (!this.form || !this.codeTextarea) {
            console.error('Form or code textarea not found!');
            return;
        }
        this.setupCodeMirror();
        this.setupFormValidation();
        this.setupPreviewFeature();
        this.setupCodeFormatting();
        this.setupCharacterCount();
        this.setupInputAnimations();
    }

    setupCodeMirror() {
        if (!this.codeTextarea) {
            console.error('Code textarea not found for CodeMirror initialization!');
            return;
        }
        this.codeEditor = CodeMirror.fromTextArea(this.codeTextarea, {
            lineNumbers: true,
            theme: 'default', // Use 'monokai' for a dark theme if preferred
            mode: 'python', // Default mode, updated later
            tabSize: 4,
            indentWithTabs: false,
            autofocus: true // Automatically focus the editor
        });

        // Update mode based on language selection
        const languageSelect = document.getElementById('language');
        if (languageSelect) {
            languageSelect.addEventListener('change', () => {
                const mode = this.getCodeMirrorMode(languageSelect.value);
                this.codeEditor.setOption('mode', mode);
            });
        } else {
            console.error('Language select element not found!');
        }
    }

    getCodeMirrorMode(language) {
        const modes = {
            'python': 'python',
            'javascript': 'javascript',
            'html': 'htmlmixed',
            'css': 'css',
            'sql': 'sql',
            'java': 'clike',
            'cpp': 'clike',
            'csharp': 'clike',
            'php': 'php',
            'ruby': 'ruby',
            'swift': 'swift',
            'kotlin': 'clike',
            'go': 'go'
        };
        return modes[language] || 'text/plain';
    }

    setupFormValidation() {
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (this.codeEditor) {
                this.codeTextarea.value = this.codeEditor.getValue();
            }

            if (this.validateForm()) {
                const submitButton = this.form.querySelector('button[type="submit"]');
                this.setLoadingState(submitButton, true);

                try {
                    const formData = new FormData(this.form);
                    const response = await fetch(this.form.action, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });

                    const data = await response.json();
                    if (data.success) {
                        this.showSuccess('Snippet created successfully!');
                        window.location.href = data.redirect;
                    } else {
                        this.showError(data.message || 'Error creating snippet');
                    }
                } catch (error) {
                    this.showError('An error occurred. Please try again.');
                } finally {
                    this.setLoadingState(submitButton, false);
                }
            }
        });
    }

    setupPreviewFeature() {
        const previewToggle = document.getElementById('preview-toggle');
        const closePreview = document.getElementById('close-preview');
        const previewContent = document.getElementById('preview-content');

        if (previewToggle && closePreview && previewContent) {
            previewToggle.addEventListener('click', () => {
                this.updatePreview();
                this.previewModal.classList.remove('hidden');
                this.previewModal.classList.add('flex');
            });

            closePreview.addEventListener('click', () => {
                this.previewModal.classList.remove('flex');
                this.previewModal.classList.add('hidden');
            });

            this.previewModal.addEventListener('click', (e) => {
                if (e.target === this.previewModal) {
                    this.previewModal.classList.remove('flex');
                    this.previewModal.classList.add('hidden');
                }
            });
        }
    }

    updatePreview() {
        const title = document.getElementById('title')?.value || '';
        const language = document.getElementById('language')?.value || '';
        const description = document.getElementById('description')?.value || '';
        const code = this.codeEditor ? this.codeEditor.getValue() : '';

        const previewContent = document.getElementById('preview-content');
        if (previewContent) {
            previewContent.innerHTML = `
                <h4 class="text-xl font-semibold text-white">${this.escapeHtml(title) || 'Untitled Snippet'}</h4>
                ${description ? `<p class="text-gray-400">${this.escapeHtml(description)}</p>` : ''}
                <div class="bg-dark-surface rounded-lg p-4">
                    <pre class="language-${language}"><code>${this.escapeHtml(code)}</code></pre>
                </div>
            `;

            Prism.highlightAllUnder(previewContent);
        }
    }

    setupCodeFormatting() {
        const formatButton = document.getElementById('format-code');
        if (formatButton) {
            formatButton.addEventListener('click', () => {
                if (this.codeEditor) {
                    const language = document.getElementById('language')?.value || '';
                    try {
                        let formattedCode = this.formatCode(this.codeEditor.getValue(), language);
                        this.codeEditor.setValue(formattedCode);
                        this.showSuccess('Code formatted successfully');
                    } catch (error) {
                        this.showError('Error formatting code');
                    }
                }
            });
        }
    }

    formatCode(code, language) {
        return code.trim();
    }

    setupCharacterCount() {
        const description = document.getElementById('description');
        const counter = document.getElementById('description-length');
        if (description && counter) {
            description.addEventListener('input', () => {
                const length = description.value.length;
                counter.textContent = length;
                counter.classList.toggle('text-red-400', length > 200);
            });
        }
    }

    setupInputAnimations() {
        const inputs = document.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('focus', () => {
                input.closest('.relative')?.classList.add('scale-[1.02]');
            });
            input.addEventListener('blur', () => {
                input.closest('.relative')?.classList.remove('scale-[1.02]');
            });
        });
    }

    validateForm() {
        let isValid = true;
        const title = document.getElementById('title');
        const code = this.codeEditor ? this.codeEditor.getValue() : '';

        if (title && title.value.trim().length < 3) {
            this.showValidationError(title, 'Title must be at least 3 characters long');
            isValid = false;
        }

        if (code.trim().length < 1) {
            this.showValidationError(this.codeTextarea, 'Code cannot be empty');
            isValid = false;
        }

        return isValid;
    }

    showValidationError(element, message) {
        if (element) {
            const messageEl = element.nextElementSibling;
            if (messageEl) {
                messageEl.textContent = message;
                messageEl.classList.remove('hidden');
                element.classList.add('border-red-500');

                setTimeout(() => {
                    messageEl.classList.add('hidden');
                    element.classList.remove('border-red-500');
                }, 3000);
            }
        }
    }

    setLoadingState(button, isLoading) {
        if (button) {
            if (isLoading) {
                button.disabled = true;
                button.innerHTML = `
                    <svg class="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Creating...
                `;
            } else {
                button.disabled = false;
                button.innerHTML = `
                    <svg class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                    </svg>
                    Create Snippet
                `;
            }
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

    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new SnippetEditor();
});