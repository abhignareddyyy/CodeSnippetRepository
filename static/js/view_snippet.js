class SnippetViewer {
    constructor() {
        this.init();
    }

    init() {
        this.setupCodeCopy();
        this.setupDeleteConfirmation();
        this.setupShareButton();
        this.setupSyntaxHighlighting();
        this.setupCodeScroll();
    }

    setupCodeCopy() {
        const copyButton = document.getElementById('copy-button');
        if (copyButton) {
            copyButton.addEventListener('click', () => {
                const codeBlock = document.getElementById('codeBlock');
                navigator.clipboard.writeText(codeBlock.textContent)
                    .then(() => this.showCopySuccess(copyButton))
                    .catch(() => this.showToast('Failed to copy code', 'error'));
            });
        }
    }

    showCopySuccess(button) {
        const originalContent = button.innerHTML;
        button.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            Copied!
        `;
        button.classList.add('text-green-400');

        setTimeout(() => {
            button.innerHTML = originalContent;
            button.classList.remove('text-green-400');
        }, 2000);   
    }

    setupDeleteConfirmation() {
        const deleteForm = document.querySelector('.delete-form');
        if (deleteForm) {
            deleteForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.showConfirmDialog({
                    title: 'Delete Snippet',
                    message: 'Are you sure you want to delete this snippet? This action cannot be undone.',
                    confirmText: 'Delete',
                    cancelText: 'Cancel',
                    confirmClass: 'bg-red-500 hover:bg-red-600',
                    onConfirm: () => deleteForm.submit()
                });
            });
        }
    }

    setupShareButton() {
        const shareButton = document.getElementById('share-button');
        if (shareButton) {
            shareButton.addEventListener('click', () => {
                const url = window.location.href;
                navigator.clipboard.writeText(url)
                    .then(() => this.showToast('Link copied to clipboard'))
                    .catch(() => this.showToast('Failed to copy link', 'error'));
            });
        }
    }

    setupSyntaxHighlighting() {
        document.addEventListener('DOMContentLoaded', () => {
            Prism.highlightAll();
        });
    }

    setupCodeScroll() {
        const codeContainer = document.getElementById('code-container');
        if (codeContainer) {
            const scrollIndicator = document.createElement('div');
            scrollIndicator.className = 'absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-accent/20 to-transparent opacity-0 transition-opacity duration-200';
            codeContainer.style.position = 'relative';
            codeContainer.appendChild(scrollIndicator);

            codeContainer.addEventListener('scroll', () => {
                const canScroll = codeContainer.scrollWidth > codeContainer.clientWidth;
                scrollIndicator.style.opacity = canScroll ? '1' : '0';
            });
        }
    }

    showConfirmDialog({ title, message, confirmText, cancelText, confirmClass, onConfirm }) {
        const dialog = document.createElement('div');
        dialog.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-fade-in';
        dialog.innerHTML = `
            <div class="bg-dark-surface-2 rounded-xl p-6 max-w-md mx-4 animate-fade-in">
                <h3 class="text-xl font-bold text-white mb-2">${title}</h3>
                <p class="text-gray-400 mb-6">${message}</p>
                <div class="flex justify-end space-x-4">
                    <button class="px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-colors duration-200 cancel-btn">
                        ${cancelText}
                    </button>
                    <button class="px-4 py-2 rounded-lg text-sm font-medium text-white ${confirmClass} transition-colors duration-200 confirm-btn">
                        ${confirmText}
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        dialog.querySelector('.cancel-btn').addEventListener('click', () => {
            this.closeDialog(dialog);
        });

        dialog.querySelector('.confirm-btn').addEventListener('click', () => {
            onConfirm();
            this.closeDialog(dialog);
        });

        dialog.addEventListener('click', (e) => {
            if (e.target === dialog) {
                this.closeDialog(dialog);
            }
        });
    }

    closeDialog(dialog) {
        dialog.classList.remove('animate-fade-in');
        dialog.classList.add('animate-fade-out');
        setTimeout(() => dialog.remove(), 300);
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

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new SnippetViewer();
});