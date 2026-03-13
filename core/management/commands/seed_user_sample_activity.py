from datetime import timedelta
from decimal import Decimal
from random import Random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from aptitude.models import (
    AptitudeCategory,
    AptitudeProblem,
    AptitudeQuizAttempt,
    AptitudeQuizResponse,
    AptitudeTopic,
)
from mock_interview.models import InterviewTurn, MockInterviewSession
from posts.models import Comment, Follow, Like, Post
from practice.models import Company, Problem, Submission, Topic, UserProblemProgress


MARKER = "[SAMPLE_SEED_PINKESH]"


class Command(BaseCommand):
    help = "Seed sample activity data (aptitude, coding, interviews, posts) for a user."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="Pinkesh", help="Username to seed sample data for.")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"].strip()
        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username.lower()}@example.com",
                "first_name": username,
            },
        )

        peers = self._ensure_peer_users()
        aptitude_count = self._seed_aptitude(user)
        solved_count, submission_count = self._seed_coding(user)
        interview_count = self._seed_interviews(user)
        post_count, like_count, comment_count = self._seed_posts(user, peers)
        following_count, follower_count = self._seed_follows(user, peers)

        self.stdout.write(self.style.SUCCESS("Sample activity seeding completed."))
        self.stdout.write(f"User: {user.username} ({'created' if user_created else 'existing'})")
        self.stdout.write(f"Aptitude quiz attempts created: {aptitude_count}")
        self.stdout.write(f"Coding solved progress items: {solved_count}")
        self.stdout.write(f"Coding submissions created: {submission_count}")
        self.stdout.write(f"Mock interview sessions created: {interview_count}")
        self.stdout.write(f"Posts created: {post_count}")
        self.stdout.write(f"Likes created: {like_count}")
        self.stdout.write(f"Comments created: {comment_count}")
        self.stdout.write(f"Following count set for {user.username}: {following_count}")
        self.stdout.write(f"Follower count set for {user.username}: {follower_count}")

    def _ensure_peer_users(self):
        peer_specs = [
            ("AaravDemo", "Aarav"),
            ("NishaDemo", "Nisha"),
            ("RohanDemo", "Rohan"),
        ]
        peers = []
        for username, first_name in peer_specs:
            peer, _ = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first_name, "email": f"{username.lower()}@example.com"},
            )
            peers.append(peer)
        return peers

    def _seed_aptitude(self, user):
        AptitudeQuizAttempt.objects.filter(
            user=user,
            achievement_label__startswith=MARKER,
        ).delete()

        problems = list(AptitudeProblem.objects.select_related("topic")[:20])
        if len(problems) < 10:
            problems.extend(self._create_fallback_aptitude_problems(missing=10 - len(problems)))

        rng = Random(2905)
        now = timezone.now()
        attempts_created = 0

        for idx in range(3):
            selected = problems[idx * 5 : (idx + 1) * 5]
            if len(selected) < 5:
                selected = (selected + problems)[:5]

            started_at = now - timedelta(days=8 - idx, hours=2 + idx)
            submitted_at = started_at + timedelta(minutes=22 + idx)

            responses_payload = []
            correct = 0
            for q_idx, problem in enumerate(selected):
                if q_idx % 3 == 0:
                    selected_option = problem.correct_option
                else:
                    selected_option = rng.choice([c for c in ["A", "B", "C", "D"] if c != problem.correct_option])
                is_correct = selected_option == problem.correct_option
                correct += int(is_correct)
                responses_payload.append((problem, selected_option, is_correct))

            score_percent = round((correct / len(selected)) * 100.0, 1)

            attempt = AptitudeQuizAttempt.objects.create(
                user=user,
                started_at=started_at,
                submitted_at=submitted_at,
                duration_minutes=30,
                question_ids=[p.id for p in selected],
                total_questions=len(selected),
                attempted_questions=len(selected),
                correct_answers=correct,
                score_percent=score_percent,
                achievement_label=f"{MARKER} Placement Drill {idx + 1}",
                status="completed",
            )

            AptitudeQuizResponse.objects.bulk_create(
                [
                    AptitudeQuizResponse(
                        attempt=attempt,
                        problem=problem,
                        selected_option=selected_option,
                        is_correct=is_correct,
                    )
                    for problem, selected_option, is_correct in responses_payload
                ]
            )
            attempts_created += 1

        return attempts_created

    def _create_fallback_aptitude_problems(self, missing):
        category, _ = AptitudeCategory.objects.get_or_create(
            name="Quantitative Aptitude",
            defaults={"description": "Auto-created sample category."},
        )
        topic, _ = AptitudeTopic.objects.get_or_create(
            category=category,
            name="Percentages",
            defaults={"description": "Auto-created sample topic."},
        )

        created = []
        current_count = AptitudeProblem.objects.filter(topic=topic).count()
        for i in range(missing):
            n = current_count + i + 1
            created.append(
                AptitudeProblem.objects.create(
                    topic=topic,
                    question_text=f"{MARKER} If a value increases by 20% then decreases by 10%, what is net change set {n}?",
                    option_a="8%",
                    option_b="10%",
                    option_c="12%",
                    option_d="15%",
                    correct_option="A",
                    explanation="1.2 x 0.9 = 1.08, so net increase is 8%.",
                    difficulty="Easy",
                )
            )
        return created

    def _seed_coding(self, user):
        Submission.objects.filter(user=user, code__contains=MARKER).delete()

        problems = list(Problem.objects.filter(is_active=True).order_by("problem_number")[:8])
        if len(problems) < 6:
            problems.extend(self._create_fallback_practice_problems(missing=6 - len(problems), creator=user))

        selected = problems[:6]
        solved_ids = set(p.id for p in selected[:4])
        now = timezone.now()

        solved_count = 0
        submission_count = 0
        for idx, problem in enumerate(selected):
            is_solved = problem.id in solved_ids
            status = "solved" if is_solved else "attempted"
            attempts = 2 if is_solved else 1

            progress, _ = UserProblemProgress.objects.update_or_create(
                user=user,
                problem=problem,
                defaults={
                    "status": status,
                    "attempts": attempts,
                    "first_solved": now - timedelta(days=idx + 1) if is_solved else None,
                },
            )
            if is_solved:
                solved_count += 1

            Submission.objects.create(
                user=user,
                problem=problem,
                code=f"# {MARKER}\n# Sample submission for {user.username}\nprint('ok')\n",
                language="python3",
                status="accepted" if is_solved else "wrong_answer",
                passed_test_cases=7 if is_solved else 3,
                total_test_cases=7,
                execution_time=12.8 if is_solved else 15.9,
                memory_used=14.2 if is_solved else 16.0,
                created_at=now - timedelta(days=idx),
            )
            submission_count += 1

            progress.last_attempted = now - timedelta(days=idx)
            progress.save(update_fields=["last_attempted"])

        return solved_count, submission_count

    def _create_fallback_practice_problems(self, missing, creator):
        topic, _ = Topic.objects.get_or_create(name="Arrays", defaults={"description": "Auto-created sample topic."})
        company, _ = Company.objects.get_or_create(name="DemoCorp", defaults={"website": "https://example.com"})

        created = []
        start_number = (Problem.objects.order_by("-problem_number").first().problem_number + 1) if Problem.objects.exists() else 1
        for i in range(missing):
            n = start_number + i
            problem = Problem.objects.create(
                problem_number=n,
                title=f"{MARKER} Sample Coding Problem {n}",
                difficulty="easy",
                description="Return the input value.",
                constraints="1 <= n <= 10^5",
                example_input="5",
                example_output="5",
                example_explanation="Identity output.",
                created_by=creator,
                is_active=True,
                total_submissions=10,
                total_accepted=7,
            )
            problem.topics.add(topic)
            problem.companies.add(company)
            created.append(problem)
        return created

    def _seed_interviews(self, user):
        MockInterviewSession.objects.filter(
            user=user,
            overall_feedback__contains=MARKER,
        ).delete()

        now = timezone.now()
        sessions_created = 0
        roles = ["Backend Developer", "Data Analyst", "Software Engineer"]
        skill_sets = ["Python, Django, REST", "SQL, Excel, Statistics", "DSA, OOP, System Design"]

        for idx in range(3):
            start_time = now - timedelta(days=14 - idx * 2, minutes=35)
            end_time = start_time + timedelta(minutes=28 + idx)
            session = MockInterviewSession.objects.create(
                user=user,
                job_role=roles[idx],
                key_skills=skill_sets[idx],
                start_time=start_time,
                end_time=end_time,
                status="COMPLETED",
                overall_feedback=f"{MARKER} Strong fundamentals with scope to improve communication clarity.",
                score=Decimal(str(68 + idx * 8)),
            )
            InterviewTurn.objects.bulk_create(
                [
                    InterviewTurn(
                        session=session,
                        turn_number=1,
                        ai_question="Tell me about a challenging project you worked on.",
                        user_answer="I built a placement prep portal with analytics and AI interviews.",
                        ai_internal_analysis="Good project ownership and technical depth.",
                        ai_follow_up_feedback="Include measurable impact in your response.",
                    ),
                    InterviewTurn(
                        session=session,
                        turn_number=2,
                        ai_question="How do you optimize a slow database query?",
                        user_answer="I inspect indexes, explain plans, and remove N+1 query patterns.",
                        ai_internal_analysis="Solid structured troubleshooting flow.",
                        ai_follow_up_feedback="Mention an example with before/after latency.",
                    ),
                    InterviewTurn(
                        session=session,
                        turn_number=3,
                        ai_question="Why should we hire you for this role?",
                        user_answer="I can ship production features quickly and iterate with feedback.",
                        ai_internal_analysis="Clear value statement, can be more specific.",
                        ai_follow_up_feedback="Add one result metric to strengthen credibility.",
                    ),
                ]
            )
            sessions_created += 1

        return sessions_created

    def _seed_posts(self, user, peers):
        Post.objects.filter(author=user, content__contains=MARKER).delete()

        posts = [
            Post.objects.create(
                author=user,
                content=f"{MARKER} Just finished a full aptitude drill today. Accuracy improved from 52% to 74%.",
            ),
            Post.objects.create(
                author=user,
                content=f"{MARKER} Solved 4 coding problems and wrapped up another mock interview round.",
            ),
        ]

        likes_created = 0
        comments_created = 0
        for post in posts:
            for peer in peers:
                _, created = Like.objects.get_or_create(post=post, user=peer)
                likes_created += int(created)

        comment_rows = [
            (posts[0], peers[0], "Great consistency. Keep tracking your weak topics too."),
            (posts[0], peers[1], "Nice jump in score. Try one hard set this weekend."),
            (posts[1], peers[2], "Strong momentum. Share which problem patterns helped most."),
            (posts[1], peers[0], "Mock interview practice is paying off."),
        ]
        for post, author, text in comment_rows:
            Comment.objects.create(post=post, author=author, content=text)
            comments_created += 1

        return len(posts), likes_created, comments_created

    def _seed_follows(self, user, peers):
        # Reset sample follow graph around the target user and demo peers.
        sample_users = [user, *peers]
        sample_ids = [u.id for u in sample_users]
        Follow.objects.filter(follower_id__in=sample_ids, following_id__in=sample_ids).delete()

        # Pinkesh follows all peers.
        for peer in peers:
            Follow.objects.get_or_create(follower=user, following=peer)

        # Two peers follow Pinkesh (third peer remains only followed-by Pinkesh).
        for peer in peers[:2]:
            Follow.objects.get_or_create(follower=peer, following=user)

        following_count = Follow.objects.filter(follower=user).count()
        follower_count = Follow.objects.filter(following=user).count()
        return following_count, follower_count
