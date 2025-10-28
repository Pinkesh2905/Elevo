from django import forms
from django.forms import inlineformset_factory
from .models import Problem, TestCase, CodeTemplate, Editorial, Topic, Company

# Dark glassmorphic theme CSS classes
INPUT_CLASS = "w-full pl-11 pr-4 py-3.5 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-[15px] placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all"

TEXTAREA_CLASS = "w-full pl-11 pr-4 py-3.5 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-[15px] placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all resize-y leading-relaxed min-h-[120px]"

TEXTAREA_CODE_CLASS = "w-full px-4 py-3.5 bg-slate-900/70 backdrop-blur-sm border border-slate-600/50 rounded-xl text-slate-100 text-[14px] placeholder-slate-500 focus:outline-none focus:border-cyan-400 focus:bg-slate-900/90 focus:ring-2 focus:ring-cyan-500/30 transition-all resize-y font-mono leading-relaxed min-h-[200px]"

SELECT_CLASS = "w-full pl-11 pr-10 py-3.5 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-[15px] focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all cursor-pointer"

MULTI_SELECT_CLASS = "w-full px-4 py-3 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-sm focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all"

NUMBER_INPUT_CLASS = "w-full pl-11 pr-4 py-3.5 bg-slate-800/50 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white text-[15px] placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:bg-slate-800/70 focus:ring-2 focus:ring-blue-500/30 transition-all"

CHECKBOX_CLASS = "w-5 h-5 bg-slate-800/50 border-2 border-slate-600/50 rounded-md text-blue-500 focus:ring-2 focus:ring-blue-500/30 focus:ring-offset-0 cursor-pointer transition-all hover:border-blue-400"

FILE_INPUT_CLASS = "block w-full text-sm text-slate-300 file:mr-4 file:py-2.5 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-500/20 file:text-blue-400 hover:file:bg-blue-500/30 file:transition-all file:cursor-pointer cursor-pointer"


class TopicForm(forms.ModelForm):
    """Form for creating/editing topics"""
    class Meta:
        model = Topic
        fields = ['name', 'slug', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'e.g., Dynamic Programming, Arrays, Trees',
                'style': 'color-scheme: dark;'
            }),
            'slug': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'e.g., dynamic-programming (auto-generated from name)',
                'style': 'color-scheme: dark;'
            }),
            'description': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 4,
                'placeholder': 'Brief description of this topic...',
                'style': 'color-scheme: dark;'
            }),
        }


class CompanyForm(forms.ModelForm):
    """Form for creating/editing companies"""
    class Meta:
        model = Company
        fields = ['name', 'slug', 'logo', 'website']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'e.g., Google, Amazon, Microsoft',
                'style': 'color-scheme: dark;'
            }),
            'slug': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'e.g., google (auto-generated from name)',
                'style': 'color-scheme: dark;'
            }),
            'website': forms.URLInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'https://www.company.com/careers',
                'style': 'color-scheme: dark;'
            }),
            'logo': forms.FileInput(attrs={
                'class': FILE_INPUT_CLASS
            }),
        }


class ProblemForm(forms.ModelForm):
    """Main form for creating/editing problems"""
    class Meta:
        model = Problem
        fields = [
            'problem_number', 'title', 'difficulty', 'description',
            'constraints', 'example_input', 'example_output', 
            'example_explanation', 'hints', 'time_complexity',
            'space_complexity', 'topics', 'companies', 'is_active'
        ]
        widgets = {
            'problem_number': forms.NumberInput(attrs={
                'class': NUMBER_INPUT_CLASS,
                'placeholder': 'e.g., 1',
                'min': '1',
                'style': 'color-scheme: dark;'
            }),
            'title': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'e.g., Two Sum, Valid Parentheses',
                'style': 'color-scheme: dark;'
            }),
            'difficulty': forms.Select(attrs={
                'class': SELECT_CLASS,
                'style': 'color-scheme: dark;'
            }),
            'description': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 8,
                'placeholder': 'Problem description (supports HTML/Markdown)...',
                'style': 'color-scheme: dark;'
            }),
            'constraints': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 4,
                'placeholder': 'e.g.,\n• 1 <= nums.length <= 10^4\n• -10^9 <= nums[i] <= 10^9',
                'style': 'color-scheme: dark;'
            }),
            'example_input': forms.Textarea(attrs={
                'class': TEXTAREA_CODE_CLASS,
                'rows': 3,
                'placeholder': 'nums = [2,7,11,15], target = 9',
                'style': 'color-scheme: dark;'
            }),
            'example_output': forms.Textarea(attrs={
                'class': TEXTAREA_CODE_CLASS,
                'rows': 3,
                'placeholder': '[0,1]',
                'style': 'color-scheme: dark;'
            }),
            'example_explanation': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 3,
                'placeholder': 'Because nums[0] + nums[1] == 9, we return [0, 1].',
                'style': 'color-scheme: dark;'
            }),
            'hints': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 4,
                'placeholder': 'One hint per line:\n• Try using a hash map\n• Think about the time complexity',
                'style': 'color-scheme: dark;'
            }),
            'time_complexity': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'e.g., O(n), O(n log n), O(n²)',
                'style': 'color-scheme: dark;'
            }),
            'space_complexity': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'e.g., O(1), O(n), O(log n)',
                'style': 'color-scheme: dark;'
            }),
            'topics': forms.SelectMultiple(attrs={
                'class': MULTI_SELECT_CLASS,
                'size': '6',
                'style': 'color-scheme: dark;'
            }),
            'companies': forms.SelectMultiple(attrs={
                'class': MULTI_SELECT_CLASS,
                'size': '6',
                'style': 'color-scheme: dark;'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': CHECKBOX_CLASS
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make topics and companies easier to select
        self.fields['topics'].queryset = Topic.objects.all().order_by('name')
        self.fields['companies'].queryset = Company.objects.all().order_by('name')
        
        # Optional fields help text
        self.fields['hints'].help_text = "Enter hints, one per line or in JSON format"
        self.fields['is_active'].help_text = "Uncheck to hide this problem from students"
        self.fields['topics'].help_text = "Hold Ctrl/Cmd to select multiple"
        self.fields['companies'].help_text = "Hold Ctrl/Cmd to select multiple"


class TestCaseForm(forms.ModelForm):
    """Form for individual test cases"""
    class Meta:
        model = TestCase
        fields = ['input_data', 'expected_output', 'is_sample', 'explanation', 'order']
        widgets = {
            'input_data': forms.Textarea(attrs={
                'class': TEXTAREA_CODE_CLASS,
                'rows': 3,
                'placeholder': 'Input for this test case',
                'style': 'color-scheme: dark;'
            }),
            'expected_output': forms.Textarea(attrs={
                'class': TEXTAREA_CODE_CLASS,
                'rows': 3,
                'placeholder': 'Expected output',
                'style': 'color-scheme: dark;'
            }),
            'is_sample': forms.CheckboxInput(attrs={
                'class': CHECKBOX_CLASS
            }),
            'explanation': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 2,
                'placeholder': 'Optional explanation for this test case',
                'style': 'color-scheme: dark;'
            }),
            'order': forms.NumberInput(attrs={
                'class': NUMBER_INPUT_CLASS,
                'min': '0',
                'value': '0',
                'style': 'color-scheme: dark;'
            }),
        }


# Formset for managing multiple test cases
TestCaseFormSet = inlineformset_factory(
    Problem,
    TestCase,
    form=TestCaseForm,
    extra=3,  # Show 3 empty forms by default
    can_delete=True,
    min_num=1,  # Require at least 1 test case
    validate_min=True,
)


class CodeTemplateForm(forms.ModelForm):
    """Form for code templates"""
    class Meta:
        model = CodeTemplate
        fields = ['language', 'template_code', 'solution_code']
        widgets = {
            'language': forms.Select(attrs={
                'class': SELECT_CLASS,
                'style': 'color-scheme: dark;'
            }),
            'template_code': forms.Textarea(attrs={
                'class': TEXTAREA_CODE_CLASS,
                'rows': 12,
                'placeholder': 'def twoSum(nums, target):\n    # Write your code here\n    pass',
                'style': 'color-scheme: dark;'
            }),
            'solution_code': forms.Textarea(attrs={
                'class': TEXTAREA_CODE_CLASS,
                'rows': 12,
                'placeholder': 'def twoSum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        ...',
                'style': 'color-scheme: dark;'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['solution_code'].help_text = "Reference solution (hidden from students)"


# Formset for managing multiple code templates (one per language)
CodeTemplateFormSet = inlineformset_factory(
    Problem,
    CodeTemplate,
    form=CodeTemplateForm,
    extra=2,  # Show 2 empty forms by default
    can_delete=True,
    min_num=1,  # Require at least 1 template
    validate_min=True,
)


class EditorialForm(forms.ModelForm):
    """Form for problem editorials/solutions"""
    class Meta:
        model = Editorial
        fields = ['approach', 'complexity_analysis', 'code_explanation', 'video_url']
        widgets = {
            'approach': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 8,
                'placeholder': 'Explain the solution approach step by step...',
                'style': 'color-scheme: dark;'
            }),
            'complexity_analysis': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 4,
                'placeholder': 'Time Complexity: O(n)\nSpace Complexity: O(n)\nExplanation: ...',
                'style': 'color-scheme: dark;'
            }),
            'code_explanation': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 6,
                'placeholder': 'Line-by-line explanation of the solution code...',
                'style': 'color-scheme: dark;'
            }),
            'video_url': forms.URLInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'https://youtube.com/watch?v=...',
                'style': 'color-scheme: dark;'
            }),
        }


class ProblemFilterForm(forms.Form):
    """Form for filtering problems in problem list"""
    difficulty = forms.ChoiceField(
        choices=[('', 'All Difficulties')] + Problem.DIFFICULTY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': SELECT_CLASS,
            'style': 'color-scheme: dark;'
        })
    )
    topic = forms.ModelChoiceField(
        queryset=Topic.objects.all(),
        required=False,
        empty_label="All Topics",
        widget=forms.Select(attrs={
            'class': SELECT_CLASS,
            'style': 'color-scheme: dark;'
        })
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=False,
        empty_label="All Companies",
        widget=forms.Select(attrs={
            'class': SELECT_CLASS,
            'style': 'color-scheme: dark;'
        })
    )
    status = forms.ChoiceField(
        choices=[
            ('', 'All Status'),
            ('solved', 'Solved'),
            ('attempted', 'Attempted'),
            ('not_attempted', 'Not Attempted'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': SELECT_CLASS,
            'style': 'color-scheme: dark;'
        })
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Search problems by title or number...',
            'style': 'color-scheme: dark;'
        })
    )


class CodeSubmissionForm(forms.Form):
    """Form for submitting code"""
    code = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': TEXTAREA_CODE_CLASS,
            'rows': 20,
            'style': 'color-scheme: dark;'
        })
    )
    language = forms.ChoiceField(
        choices=CodeTemplate.LANGUAGE_CHOICES,
        widget=forms.Select(attrs={
            'class': SELECT_CLASS,
            'style': 'color-scheme: dark;'
        })
    )