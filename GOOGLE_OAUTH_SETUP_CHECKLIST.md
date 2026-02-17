# Google OAuth Setup Checklist

## Current Status
- ✅ Frontend configured with Google Client ID
- ✅ Django settings updated with SOCIALACCOUNT_PROVIDERS
- ⏳ Google Cloud Console needs verification

---

## Action Items

### 1. Verify Google Cloud Console Configuration

**URL:** https://console.cloud.google.com/

- [ ] Go to **APIs & Services** → **Credentials**
- [ ] Find OAuth 2.0 Client ID: `156251530744-s1jbmhd87adjr99fapotk30p4sgb5mr2.apps.googleusercontent.com`
- [ ] Click to edit it
- [ ] Check **Authorized redirect URIs** section

### 2. Add Required Redirect URIs

**For Local Development (add these):**
- [ ] `http://localhost:5173`
- [ ] `http://localhost:5173/signin`
- [ ] `http://localhost:8000/accounts/google/login/callback/`
- [ ] `http://localhost:8000/accounts/allauth/google/callback/`

**For Production (add these when deploying):**
- [ ] `https://your-frontend.onrender.com`
- [ ] `https://your-frontend.onrender.com/signin`
- [ ] `https://your-backend.onrender.com/accounts/google/login/callback/`
- [ ] `https://your-backend.onrender.com/accounts/allauth/google/callback/`

### 3. Save Changes
- [ ] Click **Save** button in Google Cloud Console
- [ ] Wait 5 minutes for changes to propagate

### 4. Test Locally
- [ ] Clear browser cache (Ctrl+Shift+Delete)
- [ ] Clear cookies for localhost
- [ ] Restart Django server
- [ ] Try Google login again

### 5. Environment Variables (Optional)

If you want to use environment variables instead of hardcoding:

Add to `.env`:
```
GOOGLE_OAUTH_CLIENT_ID=156251530744-s1jbmhd87adjr99fapotk30p4sgb5mr2.apps.googleusercontent.com
GOOGLE_OAUTH_SECRET=your-secret-from-google-cloud
```

---

## Troubleshooting

**Still getting redirect_uri_mismatch?**
1. Double-check the exact URL in the error message
2. Ensure no trailing slashes mismatch
3. Check if using http vs https
4. Wait 5-10 minutes for Google to update

**Token validation fails?**
1. Ensure GOOGLE_OAUTH_SECRET is correct
2. Check that the client ID matches

**Frontend works but backend fails?**
1. Make sure backend redirect URIs are added to Google Cloud Console
2. Verify SOCIALACCOUNT_PROVIDERS in settings.py

