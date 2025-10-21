from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import redirect


class NoSignupAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Disable manual signup and force Google login instead"""
        return False  # ✅ This disables the default signup form
