# posts/forms.py

from django import forms
from .models import Post, Comment

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image']
        widgets = {
            'content': forms.Textarea(attrs={
                'placeholder': "What's on your mind?",
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none',
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'mt-2 file:bg-blue-50 file:text-blue-700 file:border-none file:rounded-lg file:px-4 file:py-2 file:cursor-pointer'
            })
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'placeholder': 'Write a comment...',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            }),
        }


class RepostForm(forms.Form):
    comment = forms.CharField(
        required=False,
        max_length=280,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Add your thoughts before reposting (optional)...',
            'class': 'w-full px-4 py-3 border border-white/20 bg-white/5 rounded-xl text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none',
        })
    )
