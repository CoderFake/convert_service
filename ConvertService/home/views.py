from django.shortcuts import render


def home(request):
    if request.user.is_authenticated:
        tab = request.GET.get("tab", "upload-file")
        if tab not in ["upload-file", "process-file"]:
            tab = "upload-file"
        context = {"tab": tab}

        if tab == "process-file":
            pass
        return render(request, 'web/home/index.html', context)
    return render(request, 'web/home/index.html')

