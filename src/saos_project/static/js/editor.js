
function approveFile(fileId) {
    if (confirm('Sei sicuro di voler approvare questo file?')) {
        fetch(`/approve/${fileId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('File approvato con successo!');
                location.reload();
            } else {
                alert('Errore durante l\'approvazione del file: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Errore:', error);
            alert('Si è verificato un errore durante l\'approvazione del file');
        });
    }
}

function rejectFile(fileId) {
    if (confirm('Sei sicuro di voler rifiutare questo file?')) {
        fetch(`/reject/${fileId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('File rifiutato con successo!');
                location.reload();
            } else {
                alert('Errore durante il rifiuto del file: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Errore:', error);
            alert('Si è verificato un errore durante il rifiuto del file');
        });
    }
}