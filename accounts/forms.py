from django import forms
from django.core.validators import MinLengthValidator
from .models import Business

class BusinessCreationForm(forms.Form):
    name = forms.CharField(max_length=100, label="Business Name")
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Default Password for Accounts",
        validators=[MinLengthValidator(4)]
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Business Address"
    )
    phone_number = forms.CharField(required=False, label="Phone Number")
    email = forms.EmailField(required=False, label="Contact Email")
    website = forms.URLField(required=False, label="Website")
    
    def clean_name(self):
        name = self.cleaned_data['name']
        if Business.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("A business with this name already exists.")
        return name