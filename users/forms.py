# elevo/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from .models import TutorApplication, UserProfile


class SignupForm(UserCreationForm):
    """
    Custom signup form for user registration, including email and role selection.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Enter your email address'
        })
    )
    
    role = forms.ChoiceField(
        choices=[('STUDENT', 'Student'), ('TUTOR', 'Tutor')],
        widget=forms.RadioSelect(attrs={'class': 'form-radio h-4 w-4 text-blue-600'}),
        initial='STUDENT',
        help_text="Select your primary role on the platform."
    )

    class Meta:
        model = User
        # CORRECTED: Removed 'password1' and 'password2' from this list.
        # UserCreationForm handles password fields automatically.
        # This list should only contain fields that exist on the User model.
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Choose a username'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        # BUG FIX: Pass *args and **kwargs to super().__init__()
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Confirm your password'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email


class CustomLoginForm(AuthenticationForm):
    """
    Custom login form with enhanced styling and email/username login support.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Username or Email',
            'autocomplete': 'off',
            'autocapitalize': 'none',
            'spellcheck': 'false',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Password',
            'autocomplete': 'off',
        })
    )
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if username and password:
            # Check if username is actually an email
            if '@' in username:
                try:
                    user = User.objects.get(email=username)
                    username = user.username
                except User.DoesNotExist:
                    pass
            
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)
        
        return self.cleaned_data


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
        }


class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['bio', 'github', 'linkedin', 'avatar', 'role', 'is_approved_tutor']
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'github': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 
                'placeholder': 'e.g., https://github.com/yourusername'
            }),
            'linkedin': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 
                'placeholder': 'e.g., https://linkedin.com/in/yourusername'
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
            }),
            'role': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'is_approved_tutor': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-blue-600 rounded'
            }),
        }
        labels = {
            'is_approved_tutor': 'Approved as Tutor (Admin Only)',
        }


class ForgotPasswordForm(forms.Form):
    """
    Form for requesting password reset.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Enter your email address'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError("No account found with this email address.")
        return email


class OTPVerificationForm(forms.Form):
    """
    Form for OTP verification during password reset.
    """
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-center text-2xl tracking-widest',
            'placeholder': '------',
            'maxlength': '6',
            'autocomplete': 'off'
        })
    )
    
    def clean_otp(self):
        otp = self.cleaned_data.get('otp')
        if not otp.isdigit():
            raise ValidationError("OTP must contain only numbers.")
        return otp


class PasswordResetForm(SetPasswordForm):
    """
    Custom password reset form with styling.
    """
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Enter new password'
        }),
        strip=False,
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Confirm new password'
        }),
        strip=False,
    )


class ResendVerificationForm(forms.Form):
    """
    Form for resending email verification.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Enter your email address'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email)
            if user.profile.is_email_verified:
                raise ValidationError("This email is already verified.")
        except User.DoesNotExist:
            raise ValidationError("No account found with this email address.")
        return email


class EmailChangeForm(forms.Form):
    """
    Form for changing email address.
    """
    new_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter new email address',
            'autocomplete': 'off',
            'autocapitalize': 'none',
            'spellcheck': 'false',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Confirm your password',
            'autocomplete': 'off',
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
    
    def clean_new_email(self):
        new_email = self.cleaned_data.get('new_email')
        if new_email == self.user.email:
            raise ValidationError("This is your current email address.")
        if User.objects.filter(email=new_email).exists():
            raise ValidationError("An account with this email already exists.")
        return new_email
    
    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.user.check_password(password):
            raise ValidationError("Invalid password.")
        return password


class TutorApplicationForm(forms.ModelForm):
    """
    Tutor application form used for tutor onboarding and resubmission.
    """

    class Meta:
        model = TutorApplication
        fields = [
            'headline',
            'expertise_areas',
            'years_experience',
            'current_organization',
            'motivation',
            'teaching_experience',
            'linkedin_url',
            'github_url',
            'portfolio_url',
            'resume',
        ]
        widgets = {
            'headline': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'placeholder': 'Short tutor headline'
            }),
            'expertise_areas': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'placeholder': 'Python, DSA, SQL, ML'
            }),
            'years_experience': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'min': 0,
                'max': 50,
            }),
            'current_organization': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'placeholder': 'Company / Institute'
            }),
            'motivation': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'rows': 4,
                'placeholder': 'Why do you want to teach on Elevo?'
            }),
            'teaching_experience': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'rows': 4,
                'placeholder': 'Relevant mentoring / teaching experience'
            }),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'placeholder': 'https://linkedin.com/in/username'
            }),
            'github_url': forms.URLInput(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'placeholder': 'https://github.com/username'
            }),
            'portfolio_url': forms.URLInput(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100',
                'placeholder': 'https://your-portfolio.com'
            }),
            'resume': forms.FileInput(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-slate-100'
            }),
        }

    def clean_years_experience(self):
        value = self.cleaned_data.get('years_experience')
        if value is not None and value > 50:
            raise ValidationError("Please enter a realistic experience value.")
        return value
