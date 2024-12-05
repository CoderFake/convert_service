
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from .forms import LoginForm, SignUpForm
import logging
logger = logging.getLogger(__name__)


def login_view(request):
    form = LoginForm(request.POST or None)

    if request.method == "POST":
        try:
            if form.is_valid():
                username = form.cleaned_data.get("username")
                password = form.cleaned_data.get("password")
                user = authenticate(username=username, password=password)
                if user is not None:
                    login(request, user)
                    return redirect("/")
                else:
                    messages.error(request, "ユーザー名またはパスワードが無効です！")
            else:
                messages.error(request, "フォームの検証中にエラーが発生しました！")
        except Exception as e:
            logger.error(e)

    return render(request, "web/accounts/login.html", {"form": form})


def register_user(request):
    msg = None
    success = False

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)

            success = True

        else:
            msg = 'Form is not valid'
    else:
        form = SignUpForm()

    return render(request, "web/accounts/register.html", {"form": form, "msg": msg, "success": success})


@login_required
def logout_user(request):
    logout(request)
    return redirect("home")