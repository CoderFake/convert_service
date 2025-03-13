import base64
import time
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.views import View
from .forms import SignUpForm
import logging

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def get_fernet_key():
    try:
        key = base64.urlsafe_b64decode(settings.HASH_KEY.encode('utf-8'))
        return Fernet(key)
    except Exception as e:
        logger.error(f"Failed to create Fernet key: {str(e)}")
        return None

def encrypt_password(password):
    f = get_fernet_key()
    if f is None:
        logger.error("Encryption failed: Fernet key is invalid")
        return None

    try:
        timestamp = str(int(time.time())).encode()
        encrypted_password = f.encrypt(password.encode() + b"|" + timestamp)
        return encrypted_password.decode()
    except Exception as e:
        logger.error(f"Error encrypting password: {str(e)}")
        return None

def decrypt_password(encrypted_password, max_age=43200):
    f = get_fernet_key()
    if f is None:
        logger.error("Decryption failed: Fernet key is invalid")
        return None

    try:
        decrypted_data = f.decrypt(encrypted_password.encode(), ttl=max_age)
        password, _ = decrypted_data.rsplit(b"|", 1)
        return password.decode()
    except Exception as e:
        logger.error(f"Error decrypting password: {str(e)}")
        return None


class LoginView(View):
    template_name = "web/accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get("username")
        password = request.POST.get("password")
        remember_password = request.POST.get("remember_pass", None)
        saved_password = request.POST.get("remember_password", None)

        next_url = request.POST.get('next', request.GET.get('next', '/'))

        try:
            if remember_password not in ["null", None, ""]:
                password = decrypt_password(remember_password)
                if password is None:
                    return JsonResponse({'status': "error",
                                         "message": "自動保存されたパスワードの有効期限が切れました。再度パスワードを入力してください。"})

            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                if saved_password == 'on':
                    if remember_password not in ["null", None, ""]:
                        encrypted_password = remember_password
                    else:
                        encrypted_password = encrypt_password(password)

                    return JsonResponse({
                        'status': "success",
                        "hash_password": encrypted_password,
                        "redirect_url": next_url
                    })
                return JsonResponse({
                    'status': "success",
                    "hash_password": None,
                    "redirect_url": next_url
                })
            else:
                return JsonResponse({'status': "error", "message": "IDまたはパスワードをもう一度確認してください。"})
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return JsonResponse({'status': "error", "message": "ログイン中にエラーが発生しました。"})


class RegisterView(View):
    template_name = "web/accounts/register.html"

    def get(self, request):
        form = SignUpForm()
        return render(request, self.template_name, {"form": form, "msg": None, "success": False})

    def post(self, request):
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)
            success = True
            return render(request, self.template_name, {"form": form, "msg": None, "success": success})
        else:
            msg = 'Form is not valid'
            return render(request, self.template_name, {"form": form, "msg": msg, "success": False})


class LogoutView(LoginRequiredMixin, View):
    def get(self, request):
        logout(request)
        return redirect("home")