class ExploreManager {
    constructor() {
        this.init();
    }

    init() {
        this.setupSnippetCards();
        this.setupVoting();
        this.setupSearchFilters();
        this.setupUserSearch();
    }

    setupSnippetCards() {
        document.querySelectorAll('.bg-dark-surface-2').forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.classList.add('transform', 'scale-102', 'shadow-lg', 'shadow-accent/5');
            });

            card.addEventListener('mouseleave', () => {
                card.classList.remove('transform', 'scale-102', 'shadow-lg', 'shadow-accent/5');
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
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest'
                        }
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

    setupSearchFilters() {
        const searchContainer = document.createElement('div');
        searchContainer.className = 'mb-6 flex space-x-4';
        searchContainer.innerHTML = `
            <select id="language-filter" 
                    class="bg-dark-surface-2 border border-gray-800 rounded-xl px-4 py-2 text-white">
                <option value="">All Languages</option>
            </select>
        `;

        const header = document.querySelector('h1').parentElement;
        header.parentElement.insertBefore(searchContainer, header.nextSibling);

        const languageFilter = document.getElementById('language-filter');

        this.populateLanguageOptions(languageFilter);

        // Initially hide all snippets since no language is selected
        this.filterSnippets('', languageFilter.value);

        languageFilter.addEventListener('change', () => {
            this.filterSnippets('', languageFilter.value);
        });
    }

    setupUserSearch() {
        const searchInput = document.getElementById('user-search');
        const searchResults = document.getElementById('search-results');
        let searchTimeout;

        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            console.log('Search query:', query);

            if (query.length < 2) {
                searchResults.innerHTML = '';
                searchResults.classList.add('hidden');
                return;
            }

            searchTimeout = setTimeout(() => {
                console.log('Fetching users for query:', query);
                fetch(`/search_users?query=${encodeURIComponent(query)}`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log('Search results:', data);
                        searchResults.innerHTML = '';
                        if (data.users.length > 0) {
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
                            searchResults.classList.remove('hidden');
                        } else {
                            searchResults.innerHTML = '<div class="p-3 text-center dark:text-ash/60 text-silver/60">No users found</div>';
                            searchResults.classList.remove('hidden');
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching search results:', error);
                        searchResults.innerHTML = '<div class="p-3 text-center text-red-400">Error loading users</div>';
                        searchResults.classList.remove('hidden');
                    });
            }, 300);
        });

        document.addEventListener('click', function(e) {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.classList.add('hidden');
            }
        });
    }

    populateLanguageOptions(select) {
        const languages = new Set();
        document.querySelectorAll('.bg-vesper-accent\\/20').forEach(span => {
            languages.add(span.textContent.trim());
        });

        [...languages].sort().forEach(language => {
            const option = document.createElement('option');
            option.value = language;
            option.textContent = language;
            select.appendChild(option);
        });
    }

    filterSnippets(searchTerm, language) {
        const normalizedSearch = searchTerm.toLowerCase();
        
        document.querySelectorAll('.bg-dark-surface-2').forEach(card => {
            const title = card.querySelector('h3').textContent.toLowerCase();
            const description = card.querySelector('p')?.textContent.toLowerCase() || '';
            const cardLanguage = card.querySelector('.bg-vesper-accent\\/20').textContent.trim();

            const matchesLanguage = language && cardLanguage === language;

            card.style.display = matchesLanguage ? 'block' : 'none';
        });
    }

    updateVoteCount(form, data) {
        const button = form.querySelector('button');
        const countSpan = button.childNodes[button.childNodes.length - 1];
        countSpan.textContent = ` ${data.upvotes || data.downvotes}`;
    }

    showVoteAnimation(button) {
        button.classList.add('scale-110');
        setTimeout(() => button.classList.remove('scale-110'), 200);
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg animate-fade-in
            ${type === 'success' ? 'bg-accent text-white' : 'bg-red-500 text-white'}`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.remove('animate-fade-in');
            toast.classList.add('animate-fade-out');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
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

document.addEventListener('DOMContentLoaded', () => {
    new ExploreManager();
});