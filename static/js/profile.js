class SnippetManager {
    constructor() {
        this.init();
    }

    init() {
        this.setupSnippetCards();
        this.setupDeleteConfirmations();
        this.setupSearch();
    }

    setupSnippetCards() {
        document.querySelectorAll('.snippet-card').forEach(card => {
            // Add hover effects
            card.addEventListener('mouseenter', () => {
                card.classList.add('transform', 'scale-102', 'shadow-lg', 'shadow-accent/5');
            });

            card.addEventListener('mouseleave', () => {
                card.classList.remove('transform', 'scale-102', 'shadow-lg', 'shadow-accent/5');
            });
        });
    }

    setupDeleteConfirmations() {
        document.querySelectorAll('.delete-snippet-form').forEach(form => {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.showDeleteConfirmation(form);
            });
        });
    }

    setupSearch() {
        const searchInput = document.getElementById('snippet-search');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(() => {
                this.filterSnippets(searchInput.value);
            }, 300));
        }
    }

    showDeleteConfirmation(form) {
        const modal = this.createModal({
            title: 'Delete Snippet',
            message: 'Are you sure you want to delete this snippet? This action cannot be undone.',
            confirmText: 'Delete',
            cancelText: 'Cancel',
            onConfirm: () => form.submit()
        });
        document.body.appendChild(modal);
    }

    createModal({ title, message, confirmText, cancelText, onConfirm }) {
        const modalWrapper = document.createElement('div');
        modalWrapper.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-fade-in';
        
        modalWrapper.innerHTML = `
            <div class="bg-dark-surface-2 rounded-xl p-6 max-w-md mx-4 animate-fade-in">
                <h3 class="text-xl font-bold text-white mb-2">${title}</h3>
                <p class="text-gray-400 mb-6">${message}</p>
                <div class="flex justify-end space-x-4">
                    <button class="cancel-btn px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-colors duration-200">
                        ${cancelText}
                    </button>
                    <button class="confirm-btn px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-500 hover:bg-red-600 transition-colors duration-200">
                        ${confirmText}
                    </button>
                </div>
            </div>
        `;

        modalWrapper.addEventListener('click', (e) => {
            if (e.target === modalWrapper) this.closeModal(modalWrapper);
        });

        modalWrapper.querySelector('.cancel-btn').addEventListener('click', () => {
            this.closeModal(modalWrapper);
        });

        modalWrapper.querySelector('.confirm-btn').addEventListener('click', () => {
            onConfirm();
            this.closeModal(modalWrapper);
        });

        return modalWrapper;
    }

    closeModal(modal) {
        modal.classList.remove('animate-fade-in');
        modal.classList.add('animate-fade-out');
        setTimeout(() => modal.remove(), 300);
    }

    filterSnippets(searchTerm) {
        const normalizedTerm = searchTerm.toLowerCase();
        document.querySelectorAll('.snippet-card').forEach(card => {
            const title = card.querySelector('.snippet-title').textContent.toLowerCase();
            const language = card.querySelector('.snippet-language').textContent.toLowerCase();
            const description = card.querySelector('.snippet-description')?.textContent.toLowerCase() || '';

            const isVisible = title.includes(normalizedTerm) || 
                            language.includes(normalizedTerm) || 
                            description.includes(normalizedTerm);

            card.classList.toggle('hidden', !isVisible);
        });
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new SnippetManager();
});