from django import forms
from .models import (
    AptitudeCategory,
    AptitudeTopic,
    AptitudeProblem,
    PracticeSet
)

# Dark glassmorphic theme CSS classes
INPUT_CLASS = "w-full pl-11 pr-4 py-3.5 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-[15px] placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all"

TEXTAREA_CLASS = "w-full pl-11 pr-4 py-3.5 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-[15px] placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all resize-y leading-relaxed min-h-[120px]"

SELECT_CLASS = "w-full pl-11 pr-10 py-3.5 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-[15px] focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all cursor-pointer"

MULTI_SELECT_CLASS = "w-full px-4 py-3 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-sm focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all"

NUMBER_INPUT_CLASS = "w-full pl-11 pr-4 py-3.5 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-[15px] placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all"


class AptitudeCategoryForm(forms.ModelForm):
    class Meta:
        model = AptitudeCategory
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Enter category name",
                "style": "color-scheme: dark;"
            }),
            "description": forms.Textarea(attrs={
                "class": TEXTAREA_CLASS,
                "rows": 4,
                "placeholder": "Brief description of this category",
                "style": "color-scheme: dark;"
            }),
        }


class AptitudeTopicForm(forms.ModelForm):
    class Meta:
        model = AptitudeTopic
        fields = ["category", "name", "description"]
        widgets = {
            "category": forms.Select(attrs={
                "class": SELECT_CLASS,
                "style": "color-scheme: dark;"
            }),
            "name": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Enter topic name",
                "style": "color-scheme: dark;"
            }),
            "description": forms.Textarea(attrs={
                "class": TEXTAREA_CLASS,
                "rows": 4,
                "placeholder": "Brief description of this topic",
                "style": "color-scheme: dark;"
            }),
        }


class AptitudeProblemForm(forms.ModelForm):
    class Meta:
        model = AptitudeProblem
        fields = [
            "topic",
            "question_text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
            "explanation",
            "difficulty",
        ]
        widgets = {
            "topic": forms.Select(attrs={
                "class": SELECT_CLASS,
                "style": "color-scheme: dark;"
            }),
            "question_text": forms.Textarea(attrs={
                "class": TEXTAREA_CLASS,
                "rows": 5,
                "placeholder": "Enter the question text",
                "style": "color-scheme: dark;"
            }),
            "option_a": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Enter option A",
                "style": "color-scheme: dark;"
            }),
            "option_b": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Enter option B",
                "style": "color-scheme: dark;"
            }),
            "option_c": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Enter option C",
                "style": "color-scheme: dark;"
            }),
            "option_d": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Enter option D",
                "style": "color-scheme: dark;"
            }),
            "correct_option": forms.Select(attrs={
                "class": SELECT_CLASS,
                "style": "color-scheme: dark;"
            }),
            "explanation": forms.Textarea(attrs={
                "class": TEXTAREA_CLASS,
                "rows": 4,
                "placeholder": "Explain the solution step by step",
                "style": "color-scheme: dark;"
            }),
            "difficulty": forms.Select(attrs={
                "class": SELECT_CLASS,
                "style": "color-scheme: dark;"
            }),
        }


class PracticeSetForm(forms.ModelForm):
    class Meta:
        model = PracticeSet
        fields = ["title", "description", "problems"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Enter practice set title",
                "style": "color-scheme: dark;"
            }),
            "description": forms.Textarea(attrs={
                "class": TEXTAREA_CLASS,
                "rows": 4,
                "placeholder": "Brief description of this practice set",
                "style": "color-scheme: dark;"
            }),
            "problems": forms.SelectMultiple(attrs={
                "class": MULTI_SELECT_CLASS,
                "size": "8",
                "style": "color-scheme: dark;"
            }),
        }