from django import forms

from .models import MockInterviewSession


class InterviewSetupForm(forms.ModelForm):
    resume_file = forms.FileField(required=False, label="Resume (PDF/DOCX/TXT)")
    interview_track = forms.ChoiceField(
        choices=[
            ("technical", "Technical Interview"),
            ("hr", "HR Interview"),
        ],
        initial="technical",
        required=True,
        label="Interview Type",
    )

    class Meta:
        model = MockInterviewSession
        fields = ["job_role", "key_skills"]
        widgets = {
            "job_role": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Software Engineer",
                }
            ),
            "key_skills": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "e.g. Python, Django, SQL",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interview_track"].widget.attrs.update(
            {
                "class": "form-control",
            }
        )

    def clean_resume_file(self):
        file_obj = self.cleaned_data.get("resume_file")
        if not file_obj:
            return None

        name = (file_obj.name or "").lower()
        ext = name.rsplit(".", 1)[-1] if "." in name else ""
        allowed_ext = {"pdf", "docx", "txt"}
        if ext not in allowed_ext:
            raise forms.ValidationError("Upload a PDF, DOCX, or TXT file.")

        if file_obj.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Maximum file size is 5 MB.")

        return file_obj
