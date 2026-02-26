"""
Django management command to reset and seed coding problems.
Deletes all existing coding problem data and seeds fresh data.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from practice.models import Topic, Company, Problem, TestCase, CodeTemplate

from .problem_data.topics_companies import TOPICS, COMPANIES
from .problem_data.problems_001_010 import PROBLEMS as P1
from .problem_data.problems_011_020 import PROBLEMS as P2
from .problem_data.problems_021_030 import PROBLEMS as P3
from .problem_data.problems_031_040 import PROBLEMS as P4
from .problem_data.problems_041_050 import PROBLEMS as P5
from .problem_data.problems_051_060 import PROBLEMS as P6
from .problem_data.problems_061_070 import PROBLEMS as P7
from .problem_data.problems_071_080 import PROBLEMS as P8
from .problem_data.problems_081_090 import PROBLEMS as P9
from .problem_data.problems_091_100 import PROBLEMS as P10

ALL_PROBLEMS = P1 + P2 + P3 + P4 + P5 + P6 + P7 + P8 + P9 + P10

LANGUAGE_MAP = {
    'python3': 'python3',
    'cpp17': 'cpp17',
    'java': 'java',
    'javascript': 'javascript',
    'c': 'c',
}


class Command(BaseCommand):
    help = 'Reset and seed all coding problems with fresh comprehensive data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-delete',
            action='store_true',
            help='Skip deletion of existing data (only add new)',
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if not options.get('no_delete'):
                self._delete_existing()
            self._seed_topics()
            self._seed_companies()
            self._seed_problems()
        self.stdout.write(self.style.SUCCESS('Done! Database seeded successfully.'))

    def _delete_existing(self):
        self.stdout.write('Deleting existing data...')
        CodeTemplate.objects.all().delete()
        TestCase.objects.all().delete()
        Problem.objects.all().delete()
        Topic.objects.all().delete()
        Company.objects.all().delete()
        self.stdout.write(self.style.WARNING('  All existing data deleted.'))

    def _seed_topics(self):
        self.stdout.write('Seeding topics...')
        for name, description in TOPICS:
            Topic.objects.get_or_create(name=name, defaults={'description': description})
        self.stdout.write(self.style.SUCCESS(f'  {len(TOPICS)} topics seeded.'))

    def _seed_companies(self):
        self.stdout.write('Seeding companies...')
        for name in COMPANIES:
            Company.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS(f'  {len(COMPANIES)} companies seeded.'))

    def _seed_problems(self):
        self.stdout.write(f'Seeding {len(ALL_PROBLEMS)} problems...')
        topic_cache = {t.name: t for t in Topic.objects.all()}
        company_cache = {c.name: c for c in Company.objects.all()}

        for i, p_data in enumerate(ALL_PROBLEMS, 1):
            problem, created = Problem.objects.get_or_create(
                problem_number=p_data['number'],
                defaults={
                    'title': p_data['title'],
                    'difficulty': p_data['difficulty'],
                    'description': p_data['description'],
                    'constraints': p_data['constraints'],
                    'example_input': p_data['example_input'],
                    'example_output': p_data['example_output'],
                    'example_explanation': p_data['example_explanation'],
                    'hints': p_data['hints'],
                    'time_complexity': p_data['time_complexity'],
                    'space_complexity': p_data['space_complexity'],
                }
            )

            if not created:
                # Update existing
                for field in ['title', 'difficulty', 'description', 'constraints',
                              'example_input', 'example_output', 'example_explanation',
                              'hints', 'time_complexity', 'space_complexity']:
                    setattr(problem, field, p_data[field])
                problem.save()

            # Set topics
            topics = [topic_cache[t] for t in p_data.get('topics', []) if t in topic_cache]
            problem.topics.set(topics)

            # Set companies
            companies = [company_cache[c] for c in p_data.get('companies', []) if c in company_cache]
            problem.companies.set(companies)

            # Create test cases
            problem.test_cases.all().delete()
            for tc in p_data.get('test_cases', []):
                TestCase.objects.create(
                    problem=problem,
                    input_data=tc['input'],
                    expected_output=tc['output'],
                    is_sample=tc.get('is_sample', False),
                    explanation=tc.get('explanation', ''),
                )

            # Create code templates
            problem.code_templates.all().delete()
            for lang_key, template_data in p_data.get('templates', {}).items():
                lang = LANGUAGE_MAP.get(lang_key, lang_key)
                CodeTemplate.objects.create(
                    problem=problem,
                    language=lang,
                    template_code=template_data['starter'],
                    solution_code=template_data['solution'],
                )

            if i % 10 == 0:
                self.stdout.write(f'  {i}/{len(ALL_PROBLEMS)} problems seeded...')

        self.stdout.write(self.style.SUCCESS(
            f'  {len(ALL_PROBLEMS)} problems seeded with test cases and code templates.'
        ))
