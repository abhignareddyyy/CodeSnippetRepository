class SnippetExploreViewer {
    constructor(snippetId) {
        this.snippetId = snippetId; // Store snippetId from template
        this.init();
    }

    init() {
        this.setupCodeCopy();
        this.setupShareButton();
        this.setupSyntaxHighlighting();
        this.setupCodeScroll();
        this.setupComments();
        this.setupReplies(); // New method for reply functionality
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

    setupComments() {
        document.getElementById('comment-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const content = document.getElementById('comment-content').value;
            
            if (!content.trim()) {
                this.showToast('Please enter a comment', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/comments', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        snippet_id: this.snippetId,
                        content: content
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    location.reload();
                } else {
                    this.showToast(data.error || 'Failed to post comment', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                this.showToast('Failed to post comment', 'error');
            }
        });
    }

    setupReplies() {
        // Since replies use onclick, we'll handle them globally but integrate with class
        window.toggleReplyForm = (commentId) => {
            const form = document.getElementById(`reply-form-${commentId}`);
            form.classList.toggle('hidden');
        };

        window.submitReply = async (commentId) => {
            const form = document.getElementById(`reply-form-${commentId}`);
            const content = form.querySelector('textarea').value;
            
            if (!content.trim()) {
                this.showToast('Please enter a reply', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/comments', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        snippet_id: this.snippetId,
                        parent_id: commentId,
                        content: content
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    location.reload();
                } else {
                    this.showToast(data.error || 'Failed to post reply', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                this.showToast('Failed to post reply', 'error');
            }
        };
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
    new SnippetExploreViewer(snippetId); // snippetId must be defined globally or passed another way
});