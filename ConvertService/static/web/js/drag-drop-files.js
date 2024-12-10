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
            const validationResult = typeValidation(file);
            if (validationResult.valid) {
                const li = createListItem(file, listContainer, listSection, submitBtn);
                listContainer.append(li);
                simulateUpload(li, listSection);
            } else {
                createToast("error", validationResult.message);
            }
        });

        checkFiles(listContainer, listSection, submitBtn);
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
                    <button class="btn btn-danger btn-sm cancel-upload" type="button" style="position: unset !important;">
                        <i class="fa fa-trash"></i>
                    </button>
                </div>
            </div>
        `);

        li.find('.cancel-upload').on('click', function () {
            li.remove();
            checkFiles(listContainer, listSection, submitBtn);
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
        submitBtn.toggleClass('d-none', !hasFiles);
        if (!hasFiles) {
            listSection.hide();
        }
    }

    function typeValidation(file) {
        const validTypes = [
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/json',
            'application/csv',
            'application/xml',
            'text/xml',
            'application/pdf',
            'text/csv'
        ];
        if (!validTypes.includes(file.type)) {
            return { valid: false, message: `${file.name} はサポートされていないファイル形式です。` };
        } else if (file.size > 5 * 1024 * 1024) {
            return { valid: false, message: `${file.name} のファイルサイズが5MBを超えています。` };
        }
        return { valid: true };
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
    $('.submit-btn').on('click', function (e) {
        e.preventDefault();

        const parentProcess = $(this).closest('.process');
        const loader = parentProcess.find('.lds-roller');

        if (loader.hasClass('d-none')) {
            loader.removeClass('d-none');
            $(this).attr('disabled', true);
        }

        setTimeout(() => {
            loader.addClass('d-none');
            $(this).attr('disabled', false);
            window.location.href= "/?tab=process-file";
        }, 3000);
    });
});
