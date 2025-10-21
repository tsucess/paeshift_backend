from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from .models import OTP
from .utils import generate_otp, send_otp_email, send_otp_sms, rate_limit_otp_requests

# @csrf_protect
# @require_http_methods(["GET", "POST"])
# @rate_limit_otp_requests
# def send_otp_view(request):
#     if request.method == "POST":
#         try:
#             username = request.POST["username"]

#             # Check if user exists
#             try:
#                 user = User.objects.get(username=username)
#             except User.DoesNotExist:
#                 messages.error(request, "User not found.")
#                 return render(request, "send_otp.html", {"error": "User not found."})

#             # Check if user is locked out due to too many failed attempts
#             if OTP.is_user_locked_out(user):
#                 messages.error(
#                     request,
#                     f"Account temporarily locked due to too many failed attempts. "
#                     f"Please try again after {OTP.LOCKOUT_MINUTES} minutes."
#                 )
#                 return render(request, "send_otp.html", {
#                     "error": f"Account locked. Try again after {OTP.LOCKOUT_MINUTES} minutes."
#                 })

#             # Delete any existing OTPs for this user
#             OTP.objects.filter(user=user).delete()

#             # Generate and save new OTP
#             otp_code = generate_otp()
#             OTP.objects.create(user=user, code=otp_code)

#             # Send OTP via email
#             send_otp_email(user, otp_code)

#             # If user has phone number, also send via SMS
#             if hasattr(user, 'profile') and user.profile.phone_number:
#                 send_otp_sms(user.profile.phone_number, otp_code)

#             # Store user ID in session
#             request.session["otp_user_id"] = user.id
#             messages.success(request, "OTP sent successfully. Please check your email.")
#             return redirect("verify_otp")

#         except Exception as e:
#             messages.error(request, f"Error sending OTP: {str(e)}")
#             return render(request, "send_otp.html", {"error": "Error sending OTP."})

#     return render(request, "send_otp.html")



# @csrf_protect
# @require_http_methods(["GET", "POST"])
# def verify_otp_view(request):
#     """View for verifying OTP codes with security measures"""
#     # Check if user ID is in session
#     user_id = request.session.get("otp_user_id")
#     if not user_id:
#         messages.error(request, "Session expired. Please request a new OTP.")
#         return redirect("send_otp")

#     try:
#         user = User.objects.get(id=user_id)
#     except User.DoesNotExist:
#         messages.error(request, "User not found.")
#         return redirect("send_otp")

#     # Check if user is locked out
#     if OTP.is_user_locked_out(user):
#         messages.error(
#             request,
#             f"Account temporarily locked due to too many failed attempts. "
#             f"Please try again after {OTP.LOCKOUT_MINUTES} minutes."
#         )
#         return render(request, "verify_otp.html", {
#             "error": f"Account locked. Try again after {OTP.LOCKOUT_MINUTES} minutes."
#         })

#     if request.method == "POST":
#         try:
#             code = request.POST["code"]
#             otp = OTP.objects.filter(user=user).order_by('-created_at').first()

#             if not otp:
#                 messages.error(request, "No OTP found. Please request a new one.")
#                 return redirect("send_otp")

#             if otp.code == code and otp.is_valid():
#                 # OTP is valid - mark as verified and log in user
#                 otp.mark_as_verified()
#                 login(request, user)
#                 messages.success(request, "Authentication successful.")

#                 # Clean up old OTPs for this user
#                 OTP.objects.filter(user=user).exclude(id=otp.id).delete()

#                 return redirect("dashboard")
#             else:
#                 # Invalid OTP - increment attempts counter
#                 if otp:
#                     is_locked = otp.increment_attempts()
#                     if is_locked:
#                         messages.error(
#                             request,
#                             f"Too many failed attempts. Account locked for {OTP.LOCKOUT_MINUTES} minutes."
#                         )
#                     else:
#                         remaining = OTP.MAX_ATTEMPTS - otp.attempts
#                         messages.error(
#                             request,
#                             f"Invalid or expired OTP. {remaining} attempts remaining."
#                         )
#                 else:
#                     messages.error(request, "Invalid or expired OTP.")

#                 return render(request, "verify_otp.html", {
#                     "error": "Invalid or expired OTP.",
#                     "attempts_remaining": OTP.MAX_ATTEMPTS - (otp.attempts if otp else 0)
#                 })

#         except Exception as e:
#             messages.error(request, f"Error verifying OTP: {str(e)}")
#             return render(request, "verify_otp.html", {"error": "Error verifying OTP."})

#     return render(request, "verify_otp.html")
