$(document).ready(function () {
    function initDragDrop(containerSelector) {
        const container = $(containerSelector);
        const listSection = container.find('.list-section');
        const listContainer = container.find('.list');
        const fileSelector = container.find('.drop-section');
        const buttonFileSelector = container.find('.file-selector');
        const fileSelectorInput = container.find('.file-selector-input');
        const submitBtn = container.find('.submit-btn');

        listSection.hide();

        buttonFileSelector.on('click', function (e) {
            e.preventDefault();
            fileSelectorInput.click();
        });

        fileSelectorInput.on('change', function (e) {
            if (e.target.files.length > 0) {
                handleFiles(e.target.files, listContainer, listSection, submitBtn);
            }
            this.value = '';
        });

        fileSelector.on('dragover', function (e) {
            e.preventDefault();
            e.stopPropagation();
            $(this).addClass('dragging');
        }).on('dragleave', function (e) {
            e.preventDefault();
            e.stopPropagation();
            $(this).removeClass('dragging');
        }).on('drop', function (e) {
            e.preventDefault();
            e.stopPropagation();
            $(this).removeClass('dragging');

            const files = e.originalEvent.dataTransfer.files;
            handleFiles(files, listContainer, listSection, submitBtn);
        });
    }

    function handleFiles(files, listContainer, listSection, submitBtn) {
        Array.from(files).forEach(file => {
            const formData = new FormData();
            formData.append('file', file);

            fetch('/api/upload-file/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: formData
            })
                .then(response => response.json())
                .then(result => {
                    if (result.status === 'success') {
                        const li = createListItem(file, listContainer, listSection, submitBtn);
                        listContainer.append(li);
                        checkFiles(listContainer, listSection, submitBtn);
                        simulateUpload(li, listSection);
                    } else {
                        createToast('error', result.message);
                    }
                })
                .catch(error => {
                    createToast('error', 'サーバーとの通信に失敗しました。');
                });
        });
    }

    function createListItem(file, listContainer, listSection, submitBtn) {
        const iconName = iconSelector(file.type);
        const fileSizeMB = (file.size / (1024 * 1024));
        const displayFileSize = fileSizeMB < 0.01 ? '0.01 MB' : `${fileSizeMB.toFixed(2)} MB`;

        const li = $('<li>').addClass('in-prog').html(`
            <div class="files w-100 d-flex flex-row">
                <div class="col file-icon">
                    <img src="/static/web/img/icons/${iconName}" alt="" style="width:45px; height: auto;">
                </div>
                <div class="col file-name">
                    <div class="name text-truncate">${file.name}</div>
                    <div class="file-progress">
                        <span>0%</span>
                    </div>
                    <div class="file-size">${displayFileSize}</div>
                </div>
                <div class="col col-btn d-flex justify-content-center align-items-center">
                    <button class="btn btn-danger btn-sm cancel-upload" type="button">
                        <i class="fa fa-trash"></i>
                    </button>
                </div>
            </div>
        `);

        li.find('.cancel-upload').on('click', function () {
            const fileName = li.find('.file-name .name').text();

            fetch('/api/delete-file/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({file_name: fileName})
            })
                .then(response => response.json())
                .then(result => {
                    if (result.status === 'success') {
                        li.remove();
                        checkFiles(listContainer, listSection, submitBtn);
                    } else {
                        createToast('error', result.message);
                    }
                })
                .catch(error => {
                    createToast('error', 'ファイル削除中にエラーが発生しました。');
                });
        });

        return li;
    }

    function simulateUpload(li, listSection) {
        listSection.show();
        const progressSpan = li.find('.file-progress span');
        let progress = 0;
        const interval = setInterval(() => {
            progress += 10;
            if (progress <= 100) {
                progressSpan.text(progress + '%');
                progressSpan.css('width', progress + '%');
            } else {
                clearInterval(interval);
                li.removeClass('in-prog').addClass('complete w-100');
            }
        }, 100);
    }

    function checkFiles(listContainer, listSection, submitBtn) {
        const hasFiles = listContainer.children().length > 0;
        if (hasFiles) {
            submitBtn.removeClass('d-none');
            listSection.show();
        } else {
            submitBtn.addClass('d-none');
            listSection.hide();
        }
    }

    function iconSelector(type) {
        switch (type) {
            case 'application/vnd.ms-excel':
            case 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                return 'excel.png';
            case 'application/json':
                return 'json.png';
            case 'application/csv':
            case 'text/csv':
                return 'csv.png';
            case 'application/xml':
            case 'text/xml':
                return 'xml.png';
            case 'application/pdf':
                return 'pdf.png';
            default:
                return 'file.png';
        }
    }

    initDragDrop('.container.reservation');
    initDragDrop('.container.response');
});


$(document).ready(function () {
    function initDownload(containerSelector) {
        const container = $(containerSelector);
        const submitBtn = container.find('.submit-btn');
        const parentProcess = container.find('.process');
        const loader = container.find('.lds-roller');
        const listSection = container.find('.list-section');
        const listContainer = container.find('.list');
        const fileSelectorInput = container.find('.file-selector-input');

        submitBtn.on('click', function (e) {
            e.preventDefault();

            if (loader.hasClass('d-none')) {
                loader.removeClass('d-none');
                $(this).attr('disabled', true);

                fetch('/api/process-files/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        'mode': 'dict'
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(result => {
                    if (result.status === 'success') {
                        fileSelectorInput.val('');
                        window.location.href = '/?tab=process-file';
                    } else {
                        createToast('error', result.message || 'エラーが発生しました。');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    createToast('error', 'ファイル処理中にエラーが発生しました。');
                })
                .finally(() => {
                    loader.addClass('d-none');
                    $(this).attr('disabled', false);
                });
            }
        });
    }

    initDownload('.container.reservation');
    initDownload('.container.response');
});
