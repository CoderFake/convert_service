import base64
import time
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
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



def login_view(request):
    if request.user.is_authenticated:
        return render(request, "web/home/index.html")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        remember_password = request.POST.get("remember_pass", None)
        saved_password = request.POST.get("remember_password", None)

        try:
            if remember_password not in ["null", None, ""]:
                password = decrypt_password(remember_password)
                if password is None:
                    return JsonResponse({'status': "error", "message": "自動保存されたパスワードの有効期限が切れました。再度パスワードを入力してください。"})

            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                if saved_password == 'on':
                    if remember_password not in ["null", None, ""]:
                        encrypted_password = remember_password
                    else:
                        encrypted_password = encrypt_password(password)

                    return JsonResponse({'status': "success", "hash_password": encrypted_password})
                return JsonResponse({'status': "success", "hash_password": None})
            else:
                return JsonResponse({'status': "error", "message": "IDまたはパスワードをもう一度確認してください。"})
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return JsonResponse({'status': "error", "message": "ログイン中にエラーが発生しました。"})

    return render(request, "web/accounts/login.html")



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