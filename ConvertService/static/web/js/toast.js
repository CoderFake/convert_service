function createToast(type, message) {
    const toastDetails = {
        success: {
            icon: 'fa-circle-check',
            color: 'green',
        },
        error: {
            icon: 'fa-circle-xmark',
            color: 'red',
        },
        warning: {
            icon: 'fa-triangle-exclamation',
            text: 'yellow',
        },
    };

    const detail = toastDetails[type];
    const tst = $('<li>').addClass(`tst ${type}`).html(`
    <div class="column" style="color: ${detail.color};">
        <i class="fa-solid ${detail.icon}"></i>
        <span>${message}</span>
   </div>
   <i class="fa-solid fa-xmark"></i>`);

    $(".notifications").append(tst);
    tst.find('.fa-xmark').click(function () {
        $(this).parent().remove();
    });
    setTimeout(() => tst.remove(), 5000);
}

function loadOverlay() {
    $('#LoadOverlay').fadeIn();
}

function closeOverlay() {
    setTimeout(function () {
        $('#LoadOverlay').fadeOut();
    }, 100);
}