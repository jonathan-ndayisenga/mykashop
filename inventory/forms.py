from django import forms
from .models import Product
from .models import Sale
from .models import Category

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


  # make sure your model is named Category

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500',
                    'placeholder': 'Enter category name'
                }
            )
        }
        labels = {
            'name': 'Category Name'
        }
