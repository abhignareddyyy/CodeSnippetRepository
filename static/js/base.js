// Rating functionality
function rateSnippet(snippetId, rating) {
    fetch(`/rate/${snippetId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ rating: rating })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateRatingDisplay(snippetId, data.new_rating, data.rating_count);
            updateStars(snippetId, rating);
        }
    })
    .catch(error => console.error('Error:', error));
}

function updateRatingDisplay(snippetId, newRating, ratingCount) {
    document.getElementById(`rating-${snippetId}`).textContent = newRating;
    document.getElementById(`rating-count-${snippetId}`).textContent = ratingCount;
}

function updateStars(snippetId, rating) {
    const stars = document.querySelectorAll(`.star-${snippetId}`);
    stars.forEach((star, index) => {
        star.classList.remove(index < rating ? 'far' : 'fas');
        star.classList.add(index < rating ? 'fas' : 'far');
    });
}

// Add smooth scrolling for flash messages
document.addEventListener('DOMContentLoaded', () => {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 3000);
    });
});