const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('file');
const progressBar = document.getElementById('progressBar');
const progress = document.getElementById('progress');
const message = document.getElementById('message');
const selectedFile = document.getElementById('selectedFile');

// Gestione del drag and drop
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
    document.body.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, highlight, false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, unhighlight, false);
});

function highlight(e) {
    dropZone.classList.add('dragover');
}

function unhighlight(e) {
    dropZone.classList.remove('dragover');
}

dropZone.addEventListener('drop', handleDrop, false);
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileSelect);

function handleDrop(e) {
    const dt = e.dataTransfer;
    const file = dt.files[0];
    handleFile(file);
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    handleFile(file);
}

function handleFile(file) {
    showSelectedFile(file);
    uploadFile(file);
}

function showSelectedFile(file) {
    selectedFile.style.display = 'block';
    selectedFile.textContent = `File selezionato: ${file.name}`;
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    progressBar.style.display = 'block';
    message.style.display = 'none';

    // Simula progresso upload
    let width = 0;
    const interval = setInterval(() => {
        if (width >= 90) clearInterval(interval);
        width += 5;
        progress.style.width = width + '%';
    }, 100);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        clearInterval(interval);
        progress.style.width = '100%';

        setTimeout(() => {
            progressBar.style.display = 'none';
            showMessage('success', `File "${data.original_name}" caricato con successo!`);
        }, 500);
    })
    .catch(error => {
        clearInterval(interval);
        progressBar.style.display = 'none';
        showMessage('error', 'Si è verificato un errore durante il caricamento del file.');
    });
}

function showMessage(type, text) {
    message.className = 'message ' + type;
    message.textContent = text;
    message.style.display = 'block';
}