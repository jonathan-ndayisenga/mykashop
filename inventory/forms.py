from django import forms
from .models import Product
from .models import Sale

class SaleForm(forms.Form):
    class Meta:
        model = Sale
        fields = ['product', 'quantity']

class SaleItemForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    quantity = forms.IntegerField(min_value=1)
    
    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields['product'].queryset = Product.objects.filter(business=business)
        else:
            self.fields['product'].queryset = Product.objects.none()
