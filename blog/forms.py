from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
    # Honeypot: hidden from humans with CSS, but naive bots fill in every field.
    website = forms.CharField(
        required=False,
        label="Leave this empty",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    class Meta:
        model = Comment
        fields = ["name", "email", "body"]
        labels = {"body": "Comment"}
        widgets = {
            "body": forms.Textarea(attrs={"rows": 5}),
        }

    def is_spam(self):
        return bool(self.cleaned_data.get("website"))
