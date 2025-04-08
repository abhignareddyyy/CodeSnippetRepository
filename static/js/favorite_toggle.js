/**
 * favorite_toggle.js
 * Handles client-side toggling of favorite status for snippets
 * using an AJAX request.
 */
document.addEventListener('DOMContentLoaded', () => {

    // Define the SVG content for the different star states
    // Using viewBox for better scaling and fill/stroke attributes for styling
    const filledStarSvg = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 current-color text-amber-500" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" clip-rule="evenodd" />
        </svg>`;

    const outlineStarSvg = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 current-color hover:text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
        </svg>`;


    // Find all favorite toggle buttons present on the page
    const toggleButtons = document.querySelectorAll('.favorite-toggle');

    // Attach event listener to each button
    toggleButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault(); // Prevent default button behavior

            const snippetId = this.dataset.snippetId;
            const buttonElement = this; // Keep reference to the clicked button

            // --- Visual Feedback: Disable button during request ---
            buttonElement.disabled = true;
            buttonElement.classList.add('opacity-60', 'cursor-not-allowed');
            // Temporarily remove hover effect to avoid color flash
            const currentSvg = buttonElement.querySelector('svg');
            if (currentSvg) {
                 currentSvg.classList.remove('hover:text-amber-500');
            }

            // Determine the correct endpoint URL (relative URL is usually fine)
            const toggleUrl = `/snippet/${snippetId}/toggle_favorite`;

            // --- Perform the AJAX Request ---
            fetch(toggleUrl, {
                method: 'POST',
                headers: {
                    // If using Flask-WTF or similar for CSRF, include the token.
                    // Get token from a hidden input field or meta tag in base.html.
                    // Example: 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content'),
                    'Accept': 'application/json', // We expect a JSON response
                    'X-Requested-With': 'XMLHttpRequest' // Standard header for AJAX
                }
                // No body needed for this specific toggle request
            })
            .then(response => {
                // Check if response is successful (status 200-299)
                if (!response.ok) {
                    // Try to parse error JSON from backend, otherwise use status text
                    return response.json().then(errData => {
                        // Throw an error with message from backend JSON if available
                         throw new Error(errData.error || `Server error: ${response.statusText}`);
                    }).catch(() => {
                        // If parsing JSON fails or no JSON body, throw generic error
                        throw new Error(`Request failed: ${response.status} ${response.statusText}`);
                    });
                }
                // If successful, parse the JSON body
                return response.json();
            })
            .then(data => {
                // --- Handle Successful Response ---
                if (data.success) {
                    if (data.status === 'added') {
                        // Update button to show 'Favorited' state (filled star)
                        buttonElement.innerHTML = filledStarSvg;
                        // Set ARIA attribute for accessibility
                        buttonElement.setAttribute('aria-pressed', 'true');
                        // No need to manually add text-amber-500 as it's in the SVG
                         console.log(`Snippet ${snippetId} favorited.`);
                    } else if (data.status === 'removed') {
                        // Update button to show 'Not Favorited' state (outline star)
                        buttonElement.innerHTML = outlineStarSvg;
                         // Set ARIA attribute for accessibility
                        buttonElement.setAttribute('aria-pressed', 'false');
                        // Re-add hover effect class for outline star
                         buttonElement.querySelector('svg')?.classList.add('hover:text-amber-500');
                         console.log(`Snippet ${snippetId} unfavorited.`);
                    }

                     // Optional: If on favorites page, you might want to visually remove the card upon unfavorite
                     const favoritesGrid = document.getElementById('favorites-grid');
                     if (favoritesGrid && data.status === 'removed') {
                        const cardToRemove = buttonElement.closest('.snippet-card');
                        if (cardToRemove) {
                            cardToRemove.style.transition = 'opacity 0.3s ease-out';
                            cardToRemove.style.opacity = '0';
                            setTimeout(() => {
                                cardToRemove.remove();
                                // Check if grid is now empty
                                if (favoritesGrid.children.length === 0) {
                                     const noFavoritesMessage = `
                                        <div class="col-span-full py-16 px-8 bg-gradient-to-br from-white to-indigo-50/20 dark:from-gray-900 dark:to-indigo-900/30 rounded-2xl border border-gray-200/30 dark:border-indigo-900/30 shadow-lg text-center backdrop-blur-sm">
                                            <span class="text-6xl text-amber-400 mb-6 block">★</span>
                                            <h3 class="text-2xl font-semibold text-gray-900 dark:text-white tracking-tight mb-4">No Favorites Left</h3>
                                            <p class="text-lg text-gray-600 dark:text-gray-300 font-light mb-6">You haven't added any snippets to your favorites. Browse snippets and click the star icon to save them here.</p>
                                            <a href="/" class="inline-flex items-center px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-base font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 ease-out transform hover:scale-[1.03]">Browse Snippets</a>
                                        </div>`;
                                    favoritesGrid.innerHTML = noFavoritesMessage;
                                }
                            }, 300); // Wait for fade out
                        }
                    }

                } else {
                    // --- Handle Backend Failure Reported in JSON ---
                    console.error('Failed to toggle favorite:', data.error || 'Unknown error from server.');
                    // Optional: Show a user-friendly error message (e.g., using a flash message library or simple alert)
                    alert(`Error: ${data.error || 'Could not update favorite status.'}`);
                }
            })
            .catch(error => {
                // --- Handle Network Errors or Other Fetch Issues ---
                console.error('Error during fetch:', error);
                // Optional: Show a user-friendly network error message
                 alert(`Network error: ${error.message || 'Could not reach server.'}`);
            })
            .finally(() => {
                // --- Cleanup: Re-enable button regardless of success/failure ---
                buttonElement.disabled = false;
                buttonElement.classList.remove('opacity-60', 'cursor-not-allowed');
                // Ensure hover class is correctly set based on final state (relevant for outline star)
                 const finalSvg = buttonElement.querySelector('svg');
                 if(finalSvg && finalSvg.getAttribute('fill') === 'none'){ // Check if it's the outline star
                     finalSvg.classList.add('hover:text-amber-500');
                 }
            });
        });
    });

    console.log('Favorite toggle script initialized.'); // For debugging

}); // End DOMContentLoaded