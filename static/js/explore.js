class ExploreManager {
    constructor() {
        this.init();
    }

    init() {
        this.setupSnippetCards();
        this.setupVoting();
        this.setupSearch();
        this.setupSorting();
        this.setupFollowButtons();
    }

    setupSnippetCards() {
        document.querySelectorAll('.snippet-card').forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.classList.add('transform', 'scale-102', 'shadow-lg');
            });
            card.addEventListener('mouseleave', () => {
                card.classList.remove('transform', 'scale-102', 'shadow-lg');
            });
        });
    }

    setupVoting() {
        const voteForms = document.querySelectorAll('form[action*="vote_snippet"]');
        
        voteForms.forEach(form => {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                try {
                    const response = await fetch(form.action, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    if (!response.ok) throw new Error('Network response was not ok');
                    const data = await response.json();
                    if (data.success) {
                        this.updateVoteCount(form, data);
                        this.showVoteAnimation(form.querySelector('button'));
                    } else {
                        this.showToast(data.message || 'Error voting', 'error');
                    }
                } catch (error) {
                    this.showToast('Error processing vote', 'error');
                }
            });
        });
    }

    setupSearch() {
        const searchToggle = document.getElementById('search-toggle');
        const searchDropdown = document.getElementById('search-dropdown');
        const searchInput = document.getElementById('user-search');
        const searchResults = document.getElementById('search-results');

        if (!searchToggle || !searchDropdown || !searchInput || !searchResults) {
            console.error('Search elements not found');
            return;
        }

        searchToggle.addEventListener('click', () => {
            searchDropdown.classList.toggle('hidden');
            if (!searchDropdown.classList.contains('hidden')) {
                searchInput.focus();
            }
        });

        searchInput.addEventListener('input', this.debounce(async () => {
            const query = searchInput.value.trim();
            if (query.length < 2) {
                searchResults.innerHTML = '';
                return;
            }

            try {
                const response = await fetch(`/search_users?query=${encodeURIComponent(query)}`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();

                searchResults.innerHTML = '';
                if (data.users && data.users.length > 0) {
                    data.users.forEach(user => {
                        const div = document.createElement('div');
                        div.className = 'p-3 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition-colors duration-200';
                        div.innerHTML = `
                            <a href="/user/${user.username}" class="flex items-center space-x-3">
                                <span class="font-medium dark:text-ash text-charcoal">${user.username}</span>
                                <span class="text-sm dark:text-ash/60 text-silver/60">${user.snippet_count} snippets</span>
                            </a>
                        `;
                        searchResults.appendChild(div);
                    });
                } else {
                    searchResults.innerHTML = '<div class="p-3 text-center dark:text-ash/60 text-silver/60">No users found</div>';
                }
            } catch (error) {
                console.error('Search error:', error);
                searchResults.innerHTML = '<div class="p-3 text-center text-red-400">Error loading users</div>';
            }
        }, 300));

        document.addEventListener('click', (e) => {
            if (!searchToggle.contains(e.target) && !searchDropdown.contains(e.target)) {
                searchDropdown.classList.add('hidden');
            }
        });
    }

    setupSorting() {
        const sortBy = document.getElementById('sort-by');
        if (!sortBy) return;

        sortBy.addEventListener('change', () => {
            const sortValue = sortBy.value;
            const topic = new URLSearchParams(window.location.search).get('topic') || '';
            window.location.href = `/explore?sort=${sortValue}${topic ? '&topic=' + encodeURIComponent(topic) : ''}`;
        });
    }

    setupFollowButtons() {
        const followForms = document.querySelectorAll('.follow-form');
        
        followForms.forEach(form => {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                try {
                    const response = await fetch(form.action, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    if (!response.ok) throw new Error('Network response was not ok');
                    const data = await response.json();
                    if (data.success) {
                        const button = form.querySelector('.follow-btn');
                        button.textContent = 'Following';
                        button.classList.remove('text-vesper-accent', 'hover:text-vesper-orange');
                        button.classList.add('text-gray-500', 'cursor-default');
                        button.disabled = true;
                        this.showToast(data.message, 'success');
                    } else {
                        this.showToast(data.message || 'Error following', 'error');
                    }
                } catch (error) {
                    this.showToast('Error processing follow', 'error');
                }
            });
        });
    }

    updateVoteCount(form, data) {
        const button = form.querySelector('button');
        const countSpan = button.querySelector('.vote-count');
        countSpan.textContent = data.upvotes || data.downvotes || 0;
    }

    showVoteAnimation(button) {
        button.classList.add('scale-110');
        setTimeout(() => button.classList.remove('scale-110'), 200);
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg animate-fade-in
            ${type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.classList.add('animate-fade-out');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    debounce(func, wait) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ExploreManager();
});