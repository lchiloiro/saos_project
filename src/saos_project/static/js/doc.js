document.addEventListener('DOMContentLoaded', function() {
const searchInput = document.getElementById('searchInput');
const filesGrid = document.getElementById('filesGrid');
const fileCards = document.getElementsByClassName('file-card');
const noResults = document.getElementById('noResults');
const viewButtons = document.querySelectorAll('.view-btn');

// Gestione vista griglia/lista
viewButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        viewButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filesGrid.className = 'files-grid ' + btn.dataset.view + '-view';
    });
});

// Funzione debounce per la ricerca
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Funzione di filtro
const filterFiles = debounce(function(searchTerm) {
    searchTerm = searchTerm.toLowerCase().trim();
    let visibleCards = 0;

    Array.from(fileCards).forEach(card => {
        const fileName = card.querySelector('.file-name').textContent.toLowerCase();
        const fileInfo = card.querySelector('.file-info').textContent.toLowerCase();

        if (fileName.includes(searchTerm) || fileInfo.includes(searchTerm)) {
            card.classList.remove('hidden');
            visibleCards++;
        } else {
            card.classList.add('hidden');
        }
    });

    if (visibleCards === 0) {
        noResults.classList.add('show');
    } else {
        noResults.classList.remove('show');
    }
}, 300);

// Event listener per la ricerca
searchInput.addEventListener('input', function(e) {
    filterFiles(e.target.value);
});

// Event listener per il pulsante elimina
document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', function(e) {
        const card = e.target.closest('.file-card');
        card.remove();

        // Controlla se ci sono ancora file visibili
        if (document.querySelectorAll('.file-card:not(.hidden)').length === 0) {
            noResults.classList.add('show');
        }
    });
});
});