from django import forms

class SearchForm(forms.Form):
    search_term = forms.CharField(max_length=255, required=True, label="Search Term")
    search_type = forms.ChoiceField(choices=[
        ('alias', 'Search by Alias'),
        ('definition', 'Search by Definition'),
        ('context', 'Search by Context'),
    ], required=True, label="Search Type"
    )
    context = forms.CharField(label='Context', required=False, max_length=255)