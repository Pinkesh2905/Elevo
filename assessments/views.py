from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
import json
import base64
from organizations.decorators import org_admin_required, org_member_required
from .models import Cohort, Assessment, AssessmentAssignment, AssessmentAttempt, ProctoringLog
from organizations.models import Membership

# --- Student Views ---

@login_required
@org_member_required
def assessment_list(request):
    """
    List of assessments assigned to the user's cohort(s).
    """
    user_cohorts = request.user.cohorts.filter(organization=request.user_org)
    assignments = AssessmentAssignment.objects.filter(cohort__in=user_cohorts).select_related('assessment')
    
    # Get existing attempts for these assignments
    attempts = AssessmentAttempt.objects.filter(user=request.user, assignment__in=assignments)
    attempt_dict = {a.assignment_id: a for a in attempts}
    
    context = {
        'assignments': assignments,
        'attempt_dict': attempt_dict,
        'now': timezone.now(),
    }
    return render(request, 'assessments/list.html', context)

@login_required
@org_member_required
def take_assessment(request, attempt_id):
    """
    The main interface for taking an assessment.
    """
    attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, user=request.user)
    
    if attempt.status in ['SUBMITTED', 'AUTO_SUBMITTED']:
        messages.info(request, "You have already submitted this assessment.")
        return redirect('assessments:list')
        
    if attempt.status == 'PENDING':
        attempt.status = 'IN_PROGRESS'
        attempt.start_time = timezone.now()
        attempt.save()
        
    assessment = attempt.assignment.assessment
    
    context = {
        'attempt': attempt,
        'assessment': assessment,
        'coding_problems': assessment.coding_problems.all(),
        'aptitude_problems': assessment.aptitude_problems.all(),
    }
    return render(request, 'assessments/take.html', context)

@login_required
@org_member_required
def submit_assessment(request, attempt_id):
    """
    Handle assessment submission and scoring.
    """
    attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, user=request.user)
    if attempt.status not in ['IN_PROGRESS']:
         return redirect('assessments:list')
         
    attempt.status = 'SUBMITTED'
    attempt.submit_time = timezone.now()
    # Logic for scoring would go here (or be handled via AJAX during the test)
    attempt.save()
    
    messages.success(request, f"Assessment '{attempt.assignment.assessment.title}' submitted successfully!")
    return redirect('assessments:list')

@login_required
@org_member_required
@csrf_exempt
def log_proctoring_event(request, attempt_id):
    if request.method == 'POST':
        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, user=request.user)
        try:
            data = json.loads(request.body)
            event_type = data.get('event_type')
            details = data.get('details', '')
            snapshot_data = data.get('snapshot')
            
            log = ProctoringLog.objects.create(
                attempt=attempt,
                event_type=event_type,
                details=details
            )
            
            if snapshot_data and event_type == 'WEBCAM_SNAPSHOT':
                if ';base64,' in snapshot_data:
                    format, imgstr = snapshot_data.split(';base64,')
                    ext = format.split('/')[-1]
                    log.snapshot.save(f'snap_{log.id}.{ext}', ContentFile(base64.b64decode(imgstr)), save=True)
            
            if event_type == 'BLUR':
                attempt.tab_switch_count += 1
                attempt.save()

            return JsonResponse({'status': 'logged'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)


# --- Manager/Admin Views ---

@login_required
@org_admin_required
def manage_cohorts(request):
    """
    List all cohorts in the organization.
    """
    cohorts = request.user_org.cohorts.all()
    return render(request, 'assessments/manage/cohorts.html', {'cohorts': cohorts})

@login_required
@org_admin_required
def create_cohort(request):
    """
    Create a new cohort.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        if name:
            cohort = Cohort.objects.create(
                organization=request.user_org,
                name=name,
                description=description
            )
            messages.success(request, f"Cohort '{name}' created successfully.")
            return redirect('assessments:cohort_detail', cohort_id=cohort.id)
    return render(request, 'assessments/manage/create_cohort.html')

@login_required
@org_admin_required
def cohort_detail(request, cohort_id):
    """
    View details and manage members of a cohort.
    """
    cohort = get_object_or_404(Cohort, id=cohort_id, organization=request.user_org)
    all_members = request.user_org.memberships.filter(is_active=True).select_related('user')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        if action == 'add' and user_id:
            cohort.members.add(user_id)
        elif action == 'remove' and user_id:
            cohort.members.remove(user_id)
            
    return render(request, 'assessments/manage/cohort_detail.html', {
        'cohort': cohort,
        'all_members': all_members,
        'cohort_member_ids': cohort.members.values_list('id', flat=True)
    })

@login_required
@org_admin_required
def manage_assessments(request):
    """
    List all assessments created by the organization.
    """
    assessments = request.user_org.assessments.all()
    return render(request, 'assessments/manage/assessments.html', {'assessments': assessments})

@login_required
@org_admin_required
def create_assessment(request):
    """
    Create a new assessment template.
    """
    from practice.models import Problem as CodingProblem
    from aptitude.models import AptitudeProblem

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        duration = request.POST.get('duration', 60)
        
        coding_ids = request.POST.getlist('coding_problems')
        aptitude_ids = request.POST.getlist('aptitude_problems')
        
        if title:
            assessment = Assessment.objects.create(
                organization=request.user_org,
                title=title,
                description=description,
                duration_minutes=duration,
                created_by=request.user
            )
            assessment.coding_problems.set(coding_ids)
            assessment.aptitude_problems.set(aptitude_ids)
            messages.success(request, f"Assessment '{title}' created.")
            return redirect('assessments:manage_assessments')
            
    context = {
        'coding_problems': CodingProblem.objects.filter(is_active=True),
        'aptitude_problems': AptitudeProblem.objects.all(),
    }
    return render(request, 'assessments/manage/create_assessment.html', context)

@login_required
@org_admin_required
def assign_assessment(request, assessment_id):
    """
    Assign an assessment to a cohort.
    """
    assessment = get_object_or_404(Assessment, id=assessment_id, organization=request.user_org)
    cohorts = request.user_org.cohorts.all()
    
    if request.method == 'POST':
        cohort_id = request.POST.get('cohort_id')
        start_window = request.POST.get('start_window')
        end_window = request.POST.get('end_window')
        
        if cohort_id and start_window and end_window:
            cohort = get_object_or_404(Cohort, id=cohort_id, organization=request.user_org)
            assignment = AssessmentAssignment.objects.create(
                assessment=assessment,
                cohort=cohort,
                start_window=start_window,
                end_window=end_window,
                assigned_by=request.user
            )
            
            # Pre-create attempts for all cohort members
            for member in cohort.members.all():
                AssessmentAttempt.objects.get_or_create(
                    assignment=assignment,
                    user=member
                )
                
            messages.success(request, f"Assigned '{assessment.title}' to '{cohort.name}'.")
            return redirect('assessments:manage_assessments')
            
    return render(request, 'assessments/manage/assign_assessment.html', {
        'assessment': assessment,
        'cohorts': cohorts
    })

@login_required
@org_admin_required
def assignment_results(request, assignment_id):
    """
    Leaderboard and detailed results for an assignment.
    """
    assignment = get_object_or_404(AssessmentAssignment, id=assignment_id, assessment__organization=request.user_org)
    attempts = assignment.attempts.select_related('user').order_by('-total_score')
    
    return render(request, 'assessments/manage/results.html', {
        'assignment': assignment,
        'attempts': attempts
    })
